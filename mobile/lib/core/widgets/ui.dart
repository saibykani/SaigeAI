import 'package:cupertino_ui/cupertino_ui.dart' show CupertinoSliverRefreshControl, RefreshIndicatorMode;
import 'package:material_ui/material_ui.dart';

import '../api.dart';
import '../motion.dart';
import '../resource.dart';
import '../theme.dart';
import 'dot_ring.dart';
import 'logo.dart';

class GlassCard extends StatelessWidget {
  const GlassCard({super.key, required this.child, this.padding = const EdgeInsets.all(18), this.onTap, this.color, this.radius = R.lg, this.border});
  final Widget child;
  final EdgeInsets padding;
  final VoidCallback? onTap;
  final Color? color;
  final double radius;
  final Color? border;

  @override
  Widget build(BuildContext context) {
    final box = Container(
      padding: padding,
      decoration: BoxDecoration(
        color: color ?? C.surface,
        borderRadius: BorderRadius.circular(radius),
        border: Border.all(color: border ?? C.line, width: 1),
        gradient: color == null ? const LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Color(0xFF131316), Color(0xFF0A0A0C)]) : null,
      ),
      child: child,
    );
    return onTap == null ? box : Pressable(onTap: onTap, scale: 0.97, child: box);
  }
}

class PrimaryButton extends StatelessWidget {
  const PrimaryButton({super.key, required this.label, this.onTap, this.icon, this.busy = false, this.ghost = false, this.expand = true});
  final String label;
  final VoidCallback? onTap;
  final IconData? icon;
  final bool busy;
  final bool ghost;
  final bool expand;

  @override
  Widget build(BuildContext context) {
    final fg = ghost ? C.text : Colors.white;
    return Pressable(
      onTap: busy ? null : onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 250),
        curve: Curves.easeOut,
        height: 54,
        padding: const EdgeInsets.symmetric(horizontal: 22),
        decoration: BoxDecoration(
          color: onTap == null && !busy ? C.surface3 : (ghost ? C.surface2 : C.primary),
          borderRadius: BorderRadius.circular(R.md),
          border: ghost ? Border.all(color: C.line) : null,
          boxShadow: ghost || onTap == null ? null : const [BoxShadow(color: Color(0x55E5304A), blurRadius: 22, offset: Offset(0, 8))],
        ),
        child: Row(mainAxisSize: expand ? MainAxisSize.max : MainAxisSize.min, mainAxisAlignment: MainAxisAlignment.center, children: [
          if (busy)
            DotRing(size: 24, dots: 10, color: fg)
          else ...[
            if (icon != null) ...[Icon(icon, size: 19, color: fg), const SizedBox(width: 8)],
            Text(label, style: TextStyle(color: fg, fontWeight: FontWeight.w600, fontSize: 15.5, letterSpacing: -0.2)),
          ],
        ]),
      ),
    );
  }
}

class Pill extends StatelessWidget {
  const Pill(this.text, {super.key, this.color = C.muted, this.filled = false});
  final String text;
  final Color color;
  final bool filled;
  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
        decoration: BoxDecoration(
          color: filled ? color.withValues(alpha: 0.16) : Colors.transparent,
          borderRadius: BorderRadius.circular(99),
          border: Border.all(color: color.withValues(alpha: 0.4)),
        ),
        child: Text(text, style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w600)),
      );
}

class SectionTitle extends StatelessWidget {
  const SectionTitle(this.text, {super.key, this.trailing});
  final String text;
  final Widget? trailing;
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(4, 26, 4, 12),
        child: Row(children: [Expanded(child: Text(text, style: T.h2)), ?trailing]),
      );
}

void toast(BuildContext context, String msg, {bool error = false}) {
  ScaffoldMessenger.maybeOf(context)
    ?..clearSnackBars()
    ..showSnackBar(SnackBar(
      behavior: SnackBarBehavior.floating,
      backgroundColor: C.surface3,
      margin: const EdgeInsets.fromLTRB(16, 0, 16, 96),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(R.sm), side: BorderSide(color: error ? C.bad : C.line)),
      content: Row(children: [
        Icon(error ? Icons.error_outline : Icons.check_circle_outline, color: error ? C.bad : C.good, size: 20),
        const SizedBox(width: 10),
        Expanded(child: Text(msg, style: const TextStyle(color: C.text))),
      ]),
    ));
}

class EmptyState extends StatelessWidget {
  const EmptyState({super.key, required this.icon, required this.title, required this.body, this.action, this.onAction});
  final IconData icon;
  final String title;
  final String body;
  final String? action;
  final VoidCallback? onAction;
  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Stagger(
            index: 0,
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              Container(
                width: 84,
                height: 84,
                decoration: BoxDecoration(shape: BoxShape.circle, color: C.surface2, border: Border.all(color: C.line)),
                child: Icon(icon, size: 36, color: C.primary),
              ),
              const SizedBox(height: 20),
              Text(title, style: T.h2, textAlign: TextAlign.center),
              const SizedBox(height: 8),
              Text(body, style: T.small, textAlign: TextAlign.center),
              if (action != null) ...[const SizedBox(height: 22), PrimaryButton(label: action!, onTap: onAction, expand: false)],
            ]),
          ),
        ),
      );
}

class ErrorState extends StatelessWidget {
  const ErrorState({super.key, required this.error, required this.onRetry});
  final ApiException error;
  final VoidCallback onRetry;
  @override
  Widget build(BuildContext context) => EmptyState(
        icon: error.offline ? Icons.cloud_off_rounded : Icons.error_outline_rounded,
        title: error.offline ? 'You are offline' : 'That did not work',
        body: error.message,
        action: 'Try again',
        onAction: onRetry,
      );
}

class LoadingState extends StatelessWidget {
  const LoadingState({super.key});
  @override
  Widget build(BuildContext context) => const Center(child: DotRing(size: 64, dots: 24));
}

/// Renders a [Resource] with loading / error / data states.
class ResourceView<V> extends StatelessWidget {
  const ResourceView({super.key, required this.resource, required this.builder});
  final Resource<V> resource;
  final Widget Function(BuildContext, V) builder;
  @override
  Widget build(BuildContext context) => ListenableBuilder(
        listenable: resource,
        builder: (context, _) {
          final d = resource.data;
          if (d != null) return builder(context, d);
          if (resource.error != null) return ErrorState(error: resource.error!, onRetry: resource.load);
          return const LoadingState();
        },
      );
}

/// Scroll view whose pull-to-refresh animates the Saige logo: the bowl peels away as you pull,
/// then a dotted ring spins while refreshing.
class LogoRefreshView extends StatelessWidget {
  const LogoRefreshView({super.key, required this.onRefresh, required this.slivers, this.controller});
  final Future<void> Function() onRefresh;
  final List<Widget> slivers;
  final ScrollController? controller;

  @override
  Widget build(BuildContext context) => CustomScrollView(
        controller: controller,
        physics: const BouncingScrollPhysics(parent: AlwaysScrollableScrollPhysics()),
        slivers: [
          CupertinoSliverRefreshControl(
            refreshTriggerPullDistance: 110,
            refreshIndicatorExtent: 70,
            onRefresh: () async {
              thump();
              await onRefresh();
            },
            builder: (context, mode, pulled, trigger, extent) {
              final p = (pulled / trigger).clamp(0.0, 1.0);
              final refreshing = mode == RefreshIndicatorMode.refresh || mode == RefreshIndicatorMode.done;
              return Center(
                child: refreshing
                    ? const DotRing(size: 40, dots: 14)
                    : Opacity(opacity: p, child: Transform.scale(scale: 0.5 + 0.5 * p, child: LogoMark(size: 34, t: 1, morph: p))),
              );
            },
          ),
          ...slivers,
          const SliverToBoxAdapter(child: SizedBox(height: 120)),
        ],
      );
}

String timeAgo(String? iso) {
  final d = DateTime.tryParse(iso ?? '')?.toLocal();
  if (d == null) return '';
  final diff = DateTime.now().difference(d);
  if (diff.inMinutes < 1) return 'just now';
  if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
  if (diff.inHours < 24) return '${diff.inHours}h ago';
  if (diff.inDays < 7) return '${diff.inDays}d ago';
  return '${d.day}/${d.month}/${d.year}';
}

String prettyStatus(String? s) =>
    (s ?? '').split('_').map((w) => w.isEmpty ? w : w[0] + w.substring(1).toLowerCase()).join(' ');
