import 'dart:io';

import 'package:material_ui/material_ui.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';

import '../api.dart';
import '../motion.dart';
import '../session.dart';
import '../theme.dart';
import 'dot_ring.dart';
import 'ui.dart';

/// Passes the launcher tile's icon + hero tag to the screen it opens, so the icon flies into the header.
class HeroScope extends InheritedWidget {
  const HeroScope({super.key, required this.tag, required this.icon, required this.color, required super.child});
  final String tag;
  final IconData icon;
  final Color color;
  static HeroScope? maybeOf(BuildContext c) => c.dependOnInheritedWidgetOfExactType<HeroScope>();
  @override
  bool updateShouldNotify(HeroScope old) => tag != old.tag;
}

/// Page frame for secondary screens: round back button, title, optional trailing widget, then the body.
class FeatureScaffold extends StatelessWidget {
  const FeatureScaffold({super.key, required this.title, this.subtitle, this.trailing, required this.child});
  final String title;
  final String? subtitle;
  final Widget? trailing;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final h = HeroScope.maybeOf(context);
    return Scaffold(
      backgroundColor: C.bg,
      body: NestedScrollView(
        headerSliverBuilder: (context, _) => [
          SliverAppBar.large(
            backgroundColor: C.bg,
            surfaceTintColor: Colors.transparent,
            scrolledUnderElevation: 0,
            expandedHeight: subtitle == null ? 112 : 128,
            automaticallyImplyLeading: false,
            leading: !Navigator.of(context).canPop() ? null : Padding(
              padding: const EdgeInsets.only(left: 12),
              child: Pressable(
                onTap: () => Navigator.of(context).maybePop(),
                child: Container(
                  margin: const EdgeInsets.all(6),
                  decoration: BoxDecoration(shape: BoxShape.circle, color: C.surface2),
                  child: Icon(Icons.arrow_back_ios_new_rounded, size: 17, color: C.text),
                ),
              ),
            ),
            title: Text(title, style: T.h1.copyWith(fontSize: 26), maxLines: 1, overflow: TextOverflow.ellipsis),
            actions: [
              if (h != null)
                Hero(
                  tag: h.tag,
                  child: Container(width: 40, height: 40, decoration: BoxDecoration(shape: BoxShape.circle, color: h.color.withValues(alpha: 0.18)), child: Icon(h.icon, color: h.color, size: 21)),
                ),
              if (trailing != null) Padding(padding: const EdgeInsets.only(left: 8), child: trailing),
              const SizedBox(width: 16),
            ],
          ),
          if (subtitle != null) SliverToBoxAdapter(child: Padding(padding: const EdgeInsets.fromLTRB(20, 0, 20, 6), child: Text(subtitle!, style: T.small))),
        ],
        body: child,
      ),
    );
  }
}

/// Score in a DotRing with a count-up number.
class ScoreRing extends StatelessWidget {
  const ScoreRing({super.key, required this.score, this.size = 120, this.label, this.dots = 36});
  final num score;
  final double size;
  final String? label;
  final int dots;
  @override
  Widget build(BuildContext context) {
    final v = score.toDouble().clamp(0, 100).toDouble();
    return DotRing(
      size: size,
      dots: dots,
      progress: v / 100,
      color: scoreColor(v),
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        CountUp(value: v, style: T.h1.copyWith(fontSize: size / 3.6, color: scoreColor(v))),
        if (label != null) Text(label!, style: T.label),
      ]),
    );
  }
}

/// Horizontally scrolling single-select chips with a spring-y press.
class ChipRow extends StatelessWidget {
  const ChipRow({super.key, required this.options, required this.value, required this.onChanged, this.labels, this.padding = 20});
  final double padding;
  final List<String> options;
  final String value;
  final ValueChanged<String> onChanged;
  final Map<String, String>? labels;
  @override
  Widget build(BuildContext context) => SizedBox(
        height: 40,
        child: ListView.separated(
          scrollDirection: Axis.horizontal,
          physics: const BouncingScrollPhysics(),
          padding: EdgeInsets.symmetric(horizontal: padding),
          itemCount: options.length,
          separatorBuilder: (_, _) => const SizedBox(width: 8),
          itemBuilder: (context, i) {
            final o = options[i];
            final on = o == value;
            return Pressable(
              onTap: () => onChanged(o),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 220),
                curve: Curves.easeOutCubic,
                padding: const EdgeInsets.symmetric(horizontal: 16),
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: on ? C.primary : C.surface2,
                  borderRadius: BorderRadius.circular(99),
                  border: Border.all(color: on ? C.primary : C.line),
                ),
                child: Text(labels?[o] ?? o, style: TextStyle(color: on ? C.onPrimary : C.muted, fontWeight: FontWeight.w600, fontSize: 13.5)),
              ),
            );
          },
        ),
      );
}

/// Labelled text field in the app's field style.
class LabeledField extends StatelessWidget {
  const LabeledField({super.key, required this.label, required this.controller, this.hint, this.lines = 1, this.keyboard, this.onSubmitted});
  final String label;
  final TextEditingController controller;
  final String? hint;
  final int lines;
  final TextInputType? keyboard;
  final ValueChanged<String>? onSubmitted;
  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Padding(padding: const EdgeInsets.only(left: 4, bottom: 8), child: Text(label.toUpperCase(), style: T.label)),
        TextField(
          controller: controller,
          minLines: lines,
          maxLines: lines,
          keyboardType: keyboard ?? (lines > 1 ? TextInputType.multiline : TextInputType.text),
          onSubmitted: onSubmitted,
          decoration: InputDecoration(hintText: hint),
        ),
      ]);
}

/// Thin progress bar that animates to [value] (0..1).
class BarFill extends StatelessWidget {
  const BarFill({super.key, required this.value, this.color, this.height = 8});
  final double value;
  final Color? color;
  final double height;
  @override
  Widget build(BuildContext context) => ClipRRect(
        borderRadius: BorderRadius.circular(99),
        child: Container(
          height: height,
          color: C.surface3,
          alignment: Alignment.centerLeft,
          child: TweenAnimationBuilder<double>(
            tween: Tween(begin: 0, end: value.clamp(0.0, 1.0)),
            duration: const Duration(milliseconds: 900),
            curve: const SpringCurve(damping: 9, freq: 2.4),
            builder: (context, v, _) => FractionallySizedBox(widthFactor: v.clamp(0.0, 1.0), child: Container(color: color ?? C.primary)),
          ),
        ),
      );
}

/// Centered inline busy indicator for sections.
class Busy extends StatelessWidget {
  const Busy({super.key, this.label});
  final String? label;
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.all(36),
        child: Center(child: Column(mainAxisSize: MainAxisSize.min, children: [const DotRing(size: 56, dots: 22), if (label != null) ...[const SizedBox(height: 14), Text(label!, style: T.small)]])),
      );
}

/// Downloads [path] (needs auth), writes it to the app's temp folder and opens the system share sheet
/// (Save to Drive / Files, open with, send). Returns false on failure after toasting.
Future<bool> downloadAndShare(BuildContext context, String path, {Map<String, dynamic>? query, String fallbackName = 'saige-file'}) async {
  try {
    final (bytes, name) = await Session.I.api.download(path, query: query);
    if (bytes.isEmpty) throw ApiException('The file came back empty.');
    final dir = await getTemporaryDirectory();
    final safe = (name ?? fallbackName).replaceAll(RegExp(r'[\\/:*?"<>|]'), '_');
    final f = File('${dir.path}${Platform.pathSeparator}$safe');
    await f.writeAsBytes(bytes, flush: true);
    success();
    await SharePlus.instance.share(ShareParams(files: [XFile(f.path)], title: safe));
    return true;
  } on ApiException catch (e) {
    if (context.mounted) toast(context, e.message, error: true);
  } catch (_) {
    if (context.mounted) toast(context, 'Could not save the file. Try again.', error: true);
  }
  return false;
}

/// "Saige blocked this" friendly text for truth-guard 422s, otherwise the API message.
String friendly(Object e) {
  if (e is ApiException) {
    if (e.status == 422 && e.message.startsWith('Something went wrong')) {
      return 'Saige blocked this: it would add something that is not in your verified profile.';
    }
    return e.message;
  }
  return 'Something went wrong. Try again.';
}

String num0(dynamic v) => v is num ? (v % 1 == 0 ? v.toInt().toString() : v.toStringAsFixed(1)) : '--';

/// Bullet row with a coloured dot.
class Dot extends StatelessWidget {
  const Dot(this.text, this.color, {super.key});
  final String text;
  final Color color;
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 10),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Padding(padding: const EdgeInsets.only(top: 7), child: Container(width: 7, height: 7, decoration: BoxDecoration(color: color, shape: BoxShape.circle))),
          const SizedBox(width: 12),
          Expanded(child: Text(text, style: T.body.copyWith(fontSize: 14))),
        ]),
      );
}
