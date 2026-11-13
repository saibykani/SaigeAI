import 'package:flutter/services.dart';
import 'package:material_ui/material_ui.dart';
import 'package:url_launcher/url_launcher.dart';

import '../config.dart';
import '../motion.dart';
import '../theme.dart';
import 'kit.dart';
import 'ui.dart';

/// The web app host (the API base URL without `/api`), for things that need a browser (OAuth, previews).
String webUrl([String path = '']) => AppConfig.baseUrl.replaceFirst(RegExp(r'/api/?$'), '') + path;

Future<void> openUrl(BuildContext context, String url) async {
  final ok = await launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication).catchError((_) => false);
  if (!ok && context.mounted) toast(context, 'Could not open the link.', error: true);
}

Future<void> copyText(BuildContext context, String text, {String done = 'Copied'}) async {
  await Clipboard.setData(ClipboardData(text: text));
  tap();
  if (context.mounted) toast(context, done);
}

/// Rounded modal sheet with a drag handle and keyboard-aware padding.
Future<V?> showSheet<V>(BuildContext context, Widget Function(BuildContext) builder) => showModalBottomSheet<V>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      backgroundColor: C.surface,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(R.lg))),
      builder: (context) => Padding(
        padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(22, 10, 22, 26),
          child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            Center(child: Container(width: 38, height: 4, margin: const EdgeInsets.only(bottom: 16), decoration: BoxDecoration(color: C.surface3, borderRadius: BorderRadius.circular(9)))),
            builder(context),
          ]),
        ),
      ),
    );

/// Runs an API action, toasting the friendly error on failure. Returns null on failure.
Future<V?> guarded<V>(BuildContext context, Future<V> Function() run, {String? ok}) async {
  try {
    final r = await run();
    if (ok != null && context.mounted) toast(context, ok);
    return r;
  } catch (e) {
    thump();
    if (context.mounted) toast(context, friendly(e), error: true);
    return null;
  }
}

Future<bool> confirmSheet(BuildContext context, {required String title, required String body, required String action, bool danger = false}) async {
  final r = await showSheet<bool>(
    context,
    (c) => Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Text(title, style: T.h2),
      const SizedBox(height: 8),
      Text(body, style: T.small),
      const SizedBox(height: 20),
      PrimaryButton(label: action, onTap: () => Navigator.pop(c, true)),
      const SizedBox(height: 8),
      PrimaryButton(label: 'Cancel', ghost: true, onTap: () => Navigator.pop(c, false)),
    ]),
  );
  return r == true;
}

/// Switch row used in settings lists.
class ToggleRow extends StatelessWidget {
  const ToggleRow({super.key, required this.title, this.sub, required this.value, required this.onChanged, this.icon});
  final String title;
  final String? sub;
  final bool value;
  final ValueChanged<bool>? onChanged;
  final IconData? icon;
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 10),
        child: Row(children: [
          if (icon != null) ...[Icon(icon, color: C.muted), const SizedBox(width: 14)],
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(title, style: const TextStyle(fontWeight: FontWeight.w600)), if (sub != null) Text(sub!, style: T.small)])),
          Switch(
            value: value,
            onChanged: onChanged == null
                ? null
                : (v) {
                    tick();
                    onChanged!(v);
                  },
          ),
        ]),
      );
}

/// Tappable settings-style row.
class NavRow extends StatelessWidget {
  const NavRow({super.key, required this.icon, required this.title, this.sub, this.onTap, this.color, this.trailing});
  final IconData icon;
  final String title;
  final String? sub;
  final VoidCallback? onTap;
  final Color? color;
  final Widget? trailing;
  @override
  Widget build(BuildContext context) => Pressable(
        onTap: onTap,
        scale: 0.98,
        child: Padding(
          padding: const EdgeInsets.all(18),
          child: Row(children: [
            Icon(icon, color: color ?? C.muted),
            const SizedBox(width: 14),
            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(title, style: TextStyle(fontWeight: FontWeight.w600, color: color)), if (sub != null) Text(sub!, style: T.small, maxLines: 2, overflow: TextOverflow.ellipsis)])),
            ?trailing,
            if (trailing == null && onTap != null && color == null) Icon(Icons.chevron_right_rounded, color: C.muted),
          ]),
        ),
      );
}

/// Card that hosts rows separated by hairlines.
class RowsCard extends StatelessWidget {
  const RowsCard({super.key, required this.children});
  final List<Widget> children;
  @override
  Widget build(BuildContext context) => GlassCard(
        padding: EdgeInsets.zero,
        child: Column(children: [for (final (i, w) in children.indexed) ...[if (i > 0) Divider(height: 1, color: C.line), w]]),
      );
}

/// Round tinted icon badge.
class IconBadge extends StatelessWidget {
  const IconBadge(this.icon, this.color, {super.key, this.size = 42});
  final IconData icon;
  final Color color;
  final double size;
  @override
  Widget build(BuildContext context) => Container(width: size, height: size, decoration: BoxDecoration(shape: BoxShape.circle, color: color.withValues(alpha: 0.16)), child: Icon(icon, color: color, size: size * 0.5));
}

/// Floating action button in the app style (pill with icon and label).
class PillFab extends StatelessWidget {
  const PillFab({super.key, required this.label, required this.icon, required this.onTap});
  final String label;
  final IconData icon;
  final VoidCallback onTap;
  @override
  Widget build(BuildContext context) => Pressable(
        onTap: onTap,
        child: Container(
          height: 54,
          padding: const EdgeInsets.symmetric(horizontal: 22),
          decoration: BoxDecoration(color: C.primary, borderRadius: BorderRadius.circular(99), boxShadow: [BoxShadow(color: C.primary.withValues(alpha: 0.35), blurRadius: 18, offset: const Offset(0, 8))]),
          child: Row(mainAxisSize: MainAxisSize.min, children: [Icon(icon, color: C.onPrimary, size: 20), const SizedBox(width: 8), Text(label, style: TextStyle(color: C.onPrimary, fontWeight: FontWeight.w700))]),
        ),
      );
}
