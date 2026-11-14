import 'package:material_ui/material_ui.dart';

import '../../core/motion.dart';
import '../../core/resource.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/dot_ring.dart';
import '../../core/widgets/forms.dart';
import '../../core/widgets/kit.dart';
import '../growth/growth_screen.dart';
import '../growth/insights_screen.dart';
import '../growth/learning_screen.dart';
import '../inbox/inbox_screen.dart';
import '../interviews/interviews_screen.dart';
import '../mock/mock_setup_screen.dart';
import '../network/linkedin_posts_screen.dart';
import '../network/outreach_screen.dart';
import '../network/recruiters_screen.dart';
import '../notifications/notifications_screen.dart';
import '../portfolio/portfolio_screen.dart';
import '../profile/profile_optimiser_screen.dart';
import '../profile/profile_screen.dart';
import '../resume/ats_coach_screen.dart';
import '../resume/cover_letter_screen.dart';
import '../resume/health_screen.dart';
import '../roles/admin_screen.dart';
import '../roles/talent_screen.dart';
import '../search/careers_screen.dart';
import '../search/find_jobs_screen.dart';
import '../settings/settings_screen.dart';

/// Shell-level handle for the side drawer (so any main screen's menu button can open it).
class DrawerNav {
  static final GlobalKey<ScaffoldState> key = GlobalKey<ScaffoldState>();
  static final ValueNotifier<bool> open = ValueNotifier(false);
  static void show() {
    tick();
    key.currentState?.openDrawer();
  }
}

/// Opens the profile (resumes, upload, server) as its own page.
void openProfile(BuildContext context) => pushDepth(context, (_) => const ProfileScreen());

/// Three lines that morph into an arrow while the drawer slides open.
class MenuButton extends StatefulWidget {
  const MenuButton({super.key});
  @override
  State<MenuButton> createState() => _MenuButtonState();
}

class _MenuButtonState extends State<MenuButton> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 380), value: DrawerNav.open.value ? 1 : 0);

  @override
  void initState() {
    super.initState();
    DrawerNav.open.addListener(_sync);
  }

  void _sync() => DrawerNav.open.value ? _c.forward() : _c.reverse();

  @override
  void dispose() {
    DrawerNav.open.removeListener(_sync);
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(right: 12),
        child: Pressable(
          haptic: false,
          scale: 0.9,
          onTap: DrawerNav.show,
          child: Container(
            width: 46,
            height: 46,
            decoration: BoxDecoration(shape: BoxShape.circle, color: C.surface2, border: Border.all(color: C.line)),
            child: Semantics(
              button: true,
              label: 'Open menu',
              child: AnimatedBuilder(
                animation: _c,
                builder: (context, _) => CustomPaint(painter: _BurgerPainter(Curves.easeInOutCubic.transform(_c.value), C.text)),
              ),
            ),
          ),
        ),
      );
}

class _BurgerPainter extends CustomPainter {
  _BurgerPainter(this.t, this.color);
  final double t;
  final Color color;
  @override
  void paint(Canvas canvas, Size s) {
    final p = Paint()
      ..color = color
      ..strokeWidth = 2.2
      ..strokeCap = StrokeCap.round;
    final c = s.center(Offset.zero);
    const w = 11.0;
    Offset l(Offset a, Offset b) => Offset.lerp(a, b, t)!;
    final x0 = c.dx - w;
    final x1 = c.dx + w;
    // Three bars (short middle) become an arrow: shaft stays, outer bars fold into the head.
    canvas.drawLine(l(Offset(x0, c.dy - 6), Offset(x0, c.dy)), l(Offset(x1, c.dy - 6), Offset(x0 + 7, c.dy - 7)), p);
    canvas.drawLine(l(Offset(x0, c.dy), Offset(x0, c.dy)), l(Offset(x1 - 5, c.dy), Offset(x1, c.dy)), p);
    canvas.drawLine(l(Offset(x0, c.dy + 6), Offset(x0, c.dy)), l(Offset(x1, c.dy + 6), Offset(x0 + 7, c.dy + 7)), p);
  }

  @override
  bool shouldRepaint(_BurgerPainter o) => o.t != t || o.color != color;
}

class _It {
  const _It(this.id, this.label, this.icon, this.color, {this.tab, this.build, this.url, this.badge = false});
  final String id;
  final String label;
  final IconData icon;
  final Color color;
  final int? tab; // switches the bottom bar tab
  final Widget Function()? build; // pushes a screen
  final String? url; // opens in the browser
  final bool badge;
}

class _Sec {
  const _Sec(this.id, this.title, this.icon, this.items);
  final String id;
  final String title;
  final IconData icon;
  final List<_It> items;
}

List<_Sec> _sections() {
  final rec = Session.I.isRecruiter;
  return [
    if (Session.I.isAdmin) _Sec('admin', 'Admin', Icons.shield_rounded, [_It('admin', 'Admin console', Icons.admin_panel_settings_rounded, C.bad, build: () => const AdminScreen())]),
    if (rec)
      _Sec('home', 'Hiring', Icons.groups_rounded, [
        _It('hiring', 'Hiring', Icons.groups_rounded, C.violet, tab: 0),
        _It('saige', 'Saige assistant', Icons.auto_awesome_rounded, C.primary, tab: 1),
        _It('notes', 'Notifications', Icons.notifications_active_rounded, C.warn, build: () => const NotificationsScreen(), badge: true),
        _It('inbox', 'Inbox', Icons.mark_email_unread_rounded, C.bad, build: () => const InboxScreen()),
      ])
    else
      _Sec('home', 'Home', Icons.home_rounded, [
        _It('dash', 'Dashboard', Icons.space_dashboard_rounded, C.primary, tab: 0),
        _It('notes', 'Notifications', Icons.notifications_active_rounded, C.warn, build: () => const NotificationsScreen(), badge: true),
      ]),
    if (!rec) ...[
      _Sec('jobs', 'Job search', Icons.work_rounded, [
        _It('foryou', 'Jobs for you', Icons.style_rounded, C.violet, tab: 1),
        _It('find', 'Find jobs', Icons.travel_explore_rounded, C.teal, build: () => const FindJobsScreen()),
        _It('careers', 'Career portals', Icons.business_center_rounded, C.warn, build: () => const CareersScreen()),
        _It('pipeline', 'Applications', Icons.view_kanban_rounded, C.blue, tab: 2),
        _It('interviews', 'Interviews', Icons.event_available_rounded, C.good, build: () => const InterviewsScreen()),
        _It('inbox', 'Inbox', Icons.mark_email_unread_rounded, C.bad, build: () => const InboxScreen()),
        _It('mock', 'Mock interview', Icons.record_voice_over_rounded, C.violet, build: () => const MockSetupScreen()),
      ]),
      _Sec('resume', 'Resume & ATS', Icons.description_rounded, [
        _It('resumes', 'My resumes', Icons.folder_copy_rounded, C.primary, build: () => const ProfileScreen()),
        _It('ats', 'ATS coach', Icons.bolt_rounded, C.blue, build: () => const AtsCoachScreen()),
        _It('health', 'Resume health', Icons.monitor_heart_rounded, C.good, build: () => const ResumeHealthScreen()),
        _It('cover', 'Cover letters', Icons.edit_note_rounded, C.violet, build: () => const CoverLetterScreen()),
        _It('learn', 'Learning path', Icons.school_rounded, C.teal, build: () => const LearningScreen()),
      ]),
    ],
    _Sec('network', 'Network', Icons.hub_rounded, [
      _It('recruiters', 'Recruiters', Icons.groups_rounded, C.violet, build: () => const RecruitersScreen()),
      _It('outreach', 'Outreach', Icons.send_rounded, C.blue, build: () => const OutreachScreen()),
      _It('ofollow', 'Outreach follow-ups', Icons.reply_all_rounded, C.warn, build: () => const OutreachScreen(initial: 'followups')),
      _It('lposts', 'LinkedIn posts', Icons.campaign_rounded, C.blue, build: () => const LinkedInPostsScreen()),
      _It('optim', 'Profile optimiser', Icons.auto_fix_high_rounded, C.teal, build: () => const ProfileOptimiserScreen()),
      if (!rec) _It('talent', 'Recruiters find me', Icons.visibility_rounded, C.lime, build: () => const TalentScreen()),
    ]),
    if (!rec)
      _Sec('growth', 'Growth', Icons.trending_up_rounded, [
        _It('goals', 'Weekly goals', Icons.flag_rounded, C.good, build: () => const GrowthScreen()),
        _It('insights', 'Insights', Icons.insights_rounded, C.teal, build: () => const InsightsScreen()),
        _It('ghost', 'Ghosting follow-ups', Icons.mark_chat_unread_rounded, C.warn, build: () => const GrowthScreen(initial: 'followups')),
      ]),
    _Sec('account', 'Account', Icons.manage_accounts_rounded, [
      _It('portfolio', 'Portfolio', Icons.web_rounded, C.violet, build: () => const PortfolioScreen()),
      _It('settings', 'Settings', Icons.settings_rounded, C.primary, build: () => const SettingsScreen()),
      _It('help', 'Help', Icons.help_outline_rounded, C.muted, url: '/help'),
    ]),
  ];
}

/// Grouped, collapsible navigation drawer with a staggered open animation.
class AppDrawer extends StatefulWidget {
  const AppDrawer({super.key, required this.tabIndex, required this.onTab});
  final ValueNotifier<int> tabIndex;
  final ValueChanged<int> onTab;
  @override
  State<AppDrawer> createState() => _AppDrawerState();
}

class _AppDrawerState extends State<AppDrawer> with SingleTickerProviderStateMixin {
  final _setup = Resource<Map<String, dynamic>>(() async => asMap(await Session.I.api.get('/profile/setup-status')));
  late final AnimationController _in = AnimationController(vsync: this, duration: const Duration(milliseconds: 900));
  final _collapsed = <String>{'growth', 'account'};
  late List<_Sec> _secs = _sections();

  @override
  void initState() {
    super.initState();
    _setup.load();
    _in.forward();
    DrawerNav.open.addListener(_opened);
  }

  void _opened() {
    if (DrawerNav.open.value) {
      _secs = _sections();
      _in.forward(from: 0);
      _setup.load();
      setState(() {});
    }
  }

  @override
  void dispose() {
    DrawerNav.open.removeListener(_opened);
    _setup.dispose();
    _in.dispose();
    super.dispose();
  }

  bool _active(_It it) => it.tab != null && widget.tabIndex.value == it.tab;

  void _go(_It it) {
    tap();
    final nav = Navigator.of(context);
    DrawerNav.key.currentState?.closeDrawer();
    if (it.tab != null) {
      widget.onTab(it.tab!);
    } else if (it.url != null) {
      openUrl(context, webUrl(it.url!));
    } else if (it.build != null) {
      nav.push(DepthRoute<void>(builder: (_) => HeroScope(tag: 'drawer-${it.id}', icon: it.icon, color: it.color, child: it.build!())));
    }
  }

  Widget _fade(double start, Widget child) {
    final a = CurvedAnimation(parent: _in, curve: Interval(start.clamp(0.0, 0.85), (start + 0.35).clamp(0.0, 1.0), curve: Curves.easeOutCubic));
    return AnimatedBuilder(
      animation: a,
      child: child,
      builder: (context, c) => Opacity(opacity: a.value, child: Transform.translate(offset: Offset(-24 * (1 - a.value), 0), child: c)),
    );
  }

  @override
  Widget build(BuildContext context) {
    var n = 0;
    final w = (MediaQuery.sizeOf(context).width * 0.84).clamp(280.0, 360.0);
    return Drawer(
      width: w,
      backgroundColor: C.bg,
      surfaceTintColor: Colors.transparent,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.horizontal(right: Radius.circular(32))),
      child: SafeArea(
        child: Column(children: [
          _fade(0, _Header(setup: _setup, onTap: () {
            tap();
            final ctx = context;
            DrawerNav.key.currentState?.closeDrawer();
            openProfile(ctx);
          })),
          Expanded(
            child: ValueListenableBuilder<int>(
              valueListenable: widget.tabIndex,
              builder: (context, _, _) => ListView(
                physics: const BouncingScrollPhysics(),
                padding: const EdgeInsets.fromLTRB(12, 4, 12, 8),
                children: [
                  for (final s in _secs) ...[
                    _fade(0.05 + 0.045 * n++, _SectionHeader(
                      sec: s,
                      open: !_collapsed.contains(s.id) || s.items.any(_active),
                      onTap: () {
                        tick();
                        setState(() => _collapsed.contains(s.id) ? _collapsed.remove(s.id) : _collapsed.add(s.id));
                      },
                    )),
                    AnimatedSize(
                      duration: const Duration(milliseconds: 320),
                      curve: Curves.easeOutCubic,
                      alignment: Alignment.topCenter,
                      child: (_collapsed.contains(s.id) && !s.items.any(_active))
                          ? const SizedBox(width: double.infinity)
                          : Column(children: [for (final it in s.items) _fade(0.05 + 0.045 * n++, _Tile(it: it, active: _active(it), onTap: () => _go(it)))]),
                    ),
                  ],
                ],
              ),
            ),
          ),
          Divider(height: 1, color: C.line),
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 6, 12, 8),
            child: _Tile(
              it: const _It('out', 'Sign out', Icons.logout_rounded, Color(0xFFD93025)),
              active: false,
              onTap: () async {
                thump();
                DrawerNav.key.currentState?.closeDrawer();
                await Session.I.logout();
              },
            ),
          ),
        ]),
      ),
    );
  }
}

class _Header extends StatelessWidget {
  const _Header({required this.setup, required this.onTap});
  final Resource<Map<String, dynamic>> setup;
  final VoidCallback onTap;

  String get _initials {
    final parts = Session.I.name.trim().split(RegExp(r'\s+')).where((e) => e.isNotEmpty).toList();
    if (parts.isEmpty) return 'S';
    return (parts.first[0] + (parts.length > 1 ? parts.last[0] : '')).toUpperCase();
  }

  @override
  Widget build(BuildContext context) {
    final role = Session.I.isAdmin ? 'Admin' : (Session.I.isRecruiter ? 'Recruiter' : 'Job seeker');
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 12, 12, 8),
      child: Pressable(
        scale: 0.98,
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(color: C.primarySoft, borderRadius: BorderRadius.circular(26)),
          child: Row(children: [
            ListenableBuilder(
              listenable: setup,
              builder: (context, _) {
                final comp = ((setup.data?['completeness'] as num?) ?? 0).toDouble();
                return DotRing(
                  size: 64,
                  dots: 26,
                  progress: comp / 100,
                  dotRadius: 1.7,
                  child: Container(
                    width: 38,
                    height: 38,
                    alignment: Alignment.center,
                    decoration: BoxDecoration(shape: BoxShape.circle, color: C.primary),
                    child: Text(_initials, style: TextStyle(color: C.onPrimary, fontWeight: FontWeight.w700, fontSize: 14.5)),
                  ),
                );
              },
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(Session.I.name.isEmpty ? 'Your profile' : Session.I.name, maxLines: 1, overflow: TextOverflow.ellipsis, style: T.h2.copyWith(fontSize: 17)),
                const SizedBox(height: 2),
                ListenableBuilder(
                  listenable: setup,
                  builder: (context, _) {
                    final comp = (setup.data?['completeness'] as num?)?.round();
                    return Text(comp == null ? role : '$role  ·  $comp% complete', style: T.small, maxLines: 1, overflow: TextOverflow.ellipsis);
                  },
                ),
              ]),
            ),
            Icon(Icons.chevron_right_rounded, color: C.muted),
          ]),
        ),
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({required this.sec, required this.open, required this.onTap});
  final _Sec sec;
  final bool open;
  final VoidCallback onTap;
  @override
  Widget build(BuildContext context) => Pressable(
        haptic: false,
        scale: 0.98,
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(12, 14, 8, 6),
          child: Row(children: [
            Expanded(child: Text(sec.title.toUpperCase(), style: T.label)),
            AnimatedRotation(turns: open ? 0.5 : 0, duration: const Duration(milliseconds: 280), curve: Curves.easeOutCubic, child: Icon(Icons.expand_more_rounded, size: 20, color: C.muted)),
          ]),
        ),
      );
}

class _Tile extends StatelessWidget {
  const _Tile({required this.it, required this.active, required this.onTap});
  final _It it;
  final bool active;
  final VoidCallback onTap;
  @override
  Widget build(BuildContext context) => Pressable(
        haptic: false,
        scale: 0.97,
        onTap: onTap,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 260),
          curve: Curves.easeOutCubic,
          margin: const EdgeInsets.symmetric(vertical: 1.5),
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 9),
          decoration: BoxDecoration(color: active ? it.color.withValues(alpha: C.dark ? 0.2 : 0.14) : Colors.transparent, borderRadius: BorderRadius.circular(99)),
          child: Row(children: [
            Container(
              width: 34,
              height: 34,
              decoration: BoxDecoration(shape: BoxShape.circle, color: it.color.withValues(alpha: active ? 0.28 : 0.15)),
              child: Icon(it.icon, size: 18, color: it.color),
            ),
            const SizedBox(width: 12),
            Expanded(child: Text(it.label, maxLines: 1, overflow: TextOverflow.ellipsis, style: TextStyle(fontSize: 15, fontWeight: active ? FontWeight.w700 : FontWeight.w500, color: C.text))),
            if (it.badge)
              ValueListenableBuilder<int>(
                valueListenable: Session.I.unread,
                builder: (context, n, _) => n <= 0
                    ? const SizedBox.shrink()
                    : Container(
                        padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                        decoration: BoxDecoration(color: C.primary, borderRadius: BorderRadius.circular(99)),
                        child: Text(n > 9 ? '9+' : '$n', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: C.onPrimary)),
                      ),
              ),
          ]),
        ),
      );
}
