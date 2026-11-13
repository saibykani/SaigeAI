import 'package:material_ui/material_ui.dart';

import '../../core/motion.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../applications/applications_screen.dart';
import '../assistant/assistant_screen.dart';
import '../home/home_screen.dart';
import '../jobs/jobs_screen.dart';
import '../profile/profile_screen.dart';

/// Lets any screen switch tabs (e.g. Home -> Applications).
class ShellNav {
  static final ValueNotifier<int> index = ValueNotifier(0);
  static void go(int i) => index.value = i;
}

class Shell extends StatefulWidget {
  const Shell({super.key});
  @override
  State<Shell> createState() => _ShellState();
}

class _ShellState extends State<Shell> with SingleTickerProviderStateMixin {
  final _visited = <int>{0};
  late final AnimationController _swap = AnimationController(vsync: this, duration: const Duration(milliseconds: 380), value: 1);

  @override
  void initState() {
    super.initState();
    ShellNav.index.value = 0;
    ShellNav.index.addListener(_changed);
    Session.I.refreshUnread();
  }

  void _changed() {
    _visited.add(ShellNav.index.value);
    _swap.forward(from: 0);
    setState(() {});
  }

  @override
  void dispose() {
    ShellNav.index.removeListener(_changed);
    _swap.dispose();
    super.dispose();
  }

  static const _tabs = <(IconData, IconData, String)>[
    (Icons.blur_circular_outlined, Icons.blur_circular_rounded, 'Home'),
    (Icons.style_outlined, Icons.style_rounded, 'Jobs'),
    (Icons.view_kanban_outlined, Icons.view_kanban_rounded, 'Pipeline'),
    (Icons.auto_awesome_outlined, Icons.auto_awesome_rounded, 'Saige'),
    (Icons.person_outline_rounded, Icons.person_rounded, 'Me'),
  ];

  Widget _page(int i) {
    if (!_visited.contains(i)) return const SizedBox.shrink();
    return switch (i) {
      0 => const HomeScreen(),
      1 => const JobsScreen(),
      2 => const ApplicationsScreen(),
      3 => const AssistantScreen(),
      _ => const ProfileScreen(),
    };
  }

  @override
  Widget build(BuildContext context) {
    final idx = ShellNav.index.value;
    return Scaffold(
      backgroundColor: C.bg,
      extendBody: true,
      body: AnimatedBuilder(
        animation: _swap,
        child: IndexedStack(index: idx, children: [for (var i = 0; i < 5; i++) _page(i)]),
        builder: (context, child) {
          final p = Curves.easeOutCubic.transform(_swap.value);
          return Opacity(opacity: 0.4 + 0.6 * p, child: Transform.scale(scale: 0.97 + 0.03 * p, child: child));
        },
      ),
      bottomNavigationBar: _NavBar(index: idx, onTap: (i) {
        if (i != idx) tick();
        ShellNav.go(i);
      }),
    );
  }
}

class _NavBar extends StatefulWidget {
  const _NavBar({required this.index, required this.onTap});
  final int index;
  final ValueChanged<int> onTap;
  @override
  State<_NavBar> createState() => _NavBarState();
}

class _NavBarState extends State<_NavBar> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 620));
  late final Animation<double> _lead = CurvedAnimation(parent: _c, curve: const Interval(0, 0.75, curve: Curves.easeOutCubic));
  late final Animation<double> _trail = CurvedAnimation(parent: _c, curve: const SpringCurve(damping: 6, freq: 2.2));
  int _from = 0;
  int _to = 0;

  @override
  void initState() {
    super.initState();
    _from = _to = widget.index;
    _c.value = 1;
  }

  @override
  void didUpdateWidget(_NavBar old) {
    super.didUpdateWidget(old);
    if (old.index != widget.index) {
      _from = old.index;
      _to = widget.index;
      _c.forward(from: 0);
    }
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final bottom = MediaQuery.paddingOf(context).bottom;
    return Padding(
      padding: EdgeInsets.fromLTRB(16, 0, 16, 12 + bottom),
      child: Container(
        height: 68,
        decoration: BoxDecoration(
          color: const Color(0xF2101013),
          borderRadius: BorderRadius.circular(34),
          border: Border.all(color: C.line),
          boxShadow: const [BoxShadow(color: Color(0xAA000000), blurRadius: 30, offset: Offset(0, 10))],
        ),
        child: LayoutBuilder(builder: (context, box) {
          final w = box.maxWidth / 5;
          return Stack(children: [
            // Liquid indicator: the leading edge runs ahead, the trailing edge springs after it.
            AnimatedBuilder(
              animation: _c,
              builder: (context, _) {
                final dir = _to >= _from;
                final a = _from + (_to - _from) * (dir ? _trail.value : _lead.value); // left edge
                final b = _from + (_to - _from) * (dir ? _lead.value : _trail.value); // right edge
                final left = (a < b ? a : b) * w + 6;
                final right = ((a > b ? a : b) + 1) * w - 6;
                return Positioned(
                  left: left,
                  width: (right - left).clamp(20.0, w * 3),
                  top: 8,
                  bottom: 8,
                  child: Container(decoration: BoxDecoration(color: C.primarySoft, borderRadius: BorderRadius.circular(26), border: Border.all(color: C.primary.withValues(alpha: 0.5)))),
                );
              },
            ),
            Row(children: [
              for (var i = 0; i < 5; i++)
                Expanded(child: _NavItem(icon: _ShellState._tabs[i], on: widget.index == i, onTap: () => widget.onTap(i))),
            ]),
          ]);
        }),
      ),
    );
  }
}

class _NavItem extends StatelessWidget {
  const _NavItem({required this.icon, required this.on, required this.onTap});
  final (IconData, IconData, String) icon;
  final bool on;
  final VoidCallback onTap;
  @override
  Widget build(BuildContext context) => Pressable(
        haptic: false,
        scale: 0.88,
        onTap: onTap,
        child: Center(
          child: TweenAnimationBuilder<double>(
            tween: Tween(begin: 0, end: on ? 1 : 0),
            duration: const Duration(milliseconds: 500),
            curve: springy,
            builder: (context, v, _) => Column(mainAxisSize: MainAxisSize.min, children: [
              Transform.translate(offset: Offset(0, -2 * v), child: Transform.scale(scale: 1 + 0.12 * v, child: Icon(on ? icon.$2 : icon.$1, size: 24, color: Color.lerp(C.muted, C.text, v.clamp(0.0, 1.0))))),
              const SizedBox(height: 2),
              Text(icon.$3, style: TextStyle(fontSize: 10.5, fontWeight: FontWeight.w600, color: Color.lerp(C.muted, C.text, v.clamp(0.0, 1.0)))),
            ]),
          ),
        ),
      );
}
