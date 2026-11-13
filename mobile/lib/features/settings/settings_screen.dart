import 'package:material_ui/material_ui.dart';

import '../../core/api.dart';
import '../../core/config.dart';
import '../../core/motion.dart';
import '../../core/resource.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/theme_controller.dart';
import '../../core/widgets/forms.dart';
import '../../core/widgets/kit.dart';
import '../../core/widgets/ui.dart';
import 'integrations_screen.dart';

const _langs = {'en': 'English', 'hi': 'हिन्दी', 'te': 'తెలుగు', 'ta': 'தமிழ்', 'kn': 'ಕನ್ನಡ', 'ml': 'മലയാളം'};
const _capLabels = {
  'job_discovery': ('Job discovery', 'Daily job feed and career scans'),
  'applications': ('Applications', 'Preparing and auto-applying'),
  'emails': ('Emails', 'Replies and application mail'),
  'recruiter_outreach': ('Recruiter outreach', 'Drafts and follow-ups'),
  'profile_updates': ('Profile updates', 'LinkedIn and Naukri suggestions'),
  'gmail_sync': ('Gmail sync', 'Reading recruiter replies'),
};

/// Settings: theme, assistant language, automation, privacy, integrations and sign out.
class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});
  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  String _lang = AppConfig.lang;

  @override
  Widget build(BuildContext context) => FeatureScaffold(
        title: 'Settings',
        subtitle: 'Make Saige yours',
        child: ListView(physics: const BouncingScrollPhysics(), padding: const EdgeInsets.fromLTRB(20, 0, 20, 120), children: [
          Stagger(index: 0, child: const SectionTitle('Appearance')),
          const Stagger(index: 1, child: ThemePicker()),
          const Stagger(index: 2, child: SectionTitle('Assistant language')),
          Stagger(
            index: 3,
            child: GlassCard(
              radius: R.md,
              padding: const EdgeInsets.symmetric(vertical: 14),
              child: ChipRow(options: _langs.keys.toList(), labels: _langs, value: _lang, onChanged: (v) {
                setState(() => _lang = v);
                AppConfig.setLang(v);
                tick();
              }),
            ),
          ),
          const Stagger(index: 4, child: SectionTitle('Automation')),
          const Stagger(index: 5, child: _AutomationCard()),
          const Stagger(index: 6, child: SectionTitle('Account')),
          Stagger(
            index: 7,
            child: RowsCard(children: [
              NavRow(icon: Icons.hub_rounded, title: 'Integrations', sub: 'Gmail, WhatsApp, Telegram', onTap: () => pushDepth(context, (_) => const IntegrationsScreen())),
              NavRow(icon: Icons.download_rounded, title: 'Export my data', sub: 'Everything Saige stores about you, as JSON', onTap: () => downloadAndShare(context, '/privacy/export', fallbackName: 'saige-ai-export.json')),
              NavRow(icon: Icons.delete_forever_rounded, title: 'Delete account', sub: 'Removes your data and ends all sessions', color: C.bad, onTap: () => _delete(context)),
              NavRow(icon: Icons.logout_rounded, title: 'Sign out', color: C.bad, onTap: () async {
                thump();
                Navigator.of(context).popUntil((r) => r.isFirst);
                await Session.I.logout();
              }),
            ]),
          ),
          const SizedBox(height: 20),
          Center(child: Text('Saige never invents facts and never sends anything without your approval.', style: T.small, textAlign: TextAlign.center)),
        ]),
      );

  Future<void> _delete(BuildContext context) async {
    final c = TextEditingController();
    final go = await showSheet<bool>(
      context,
      (ctx) => StatefulBuilder(
        builder: (ctx, set) => Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text('Delete your account?', style: T.h2.copyWith(color: C.bad)),
          const SizedBox(height: 8),
          Text('This permanently deletes your profile, resumes, applications and every record Saige holds. It cannot be undone. Export your data first if you want a copy.', style: T.small),
          const SizedBox(height: 14),
          LabeledField(label: 'Type DELETE to confirm', controller: c),
          const SizedBox(height: 16),
          ListenableBuilder(
            listenable: c,
            builder: (_, _) => PrimaryButton(label: 'Delete everything', onTap: c.text.trim() == 'DELETE' ? () => Navigator.pop(ctx, true) : null),
          ),
          const SizedBox(height: 8),
          PrimaryButton(label: 'Keep my account', ghost: true, onTap: () => Navigator.pop(ctx, false)),
        ]),
      ),
    );
    c.dispose();
    if (go != true || !context.mounted) return;
    try {
      await Session.I.api.request('DELETE', '/privacy/account');
      success();
      if (context.mounted) Navigator.of(context).popUntil((r) => r.isFirst);
      await Session.I.logout();
    } on ApiException catch (e) {
      if (context.mounted) toast(context, e.message, error: true);
    }
  }
}

/// Theme grid with live swatches. Tapping a theme grows it from the tap point as a circular reveal.
class ThemePicker extends StatelessWidget {
  const ThemePicker({super.key});

  @override
  Widget build(BuildContext context) => ListenableBuilder(
        listenable: ThemeController.I,
        builder: (context, _) {
          final mode = ThemeController.I.mode;
          return Column(children: [
            _Tile(
              onSelect: (o) => ThemeController.I.select('system', origin: o),
              on: mode == 'system',
              title: 'Follow system',
              note: 'Light by day, dark by night',
              preview: Row(children: [Expanded(child: _Swatch(palettes[0])), Expanded(child: _Swatch(palettes[1]))]),
            ),
            const SizedBox(height: 10),
            GridView.count(
              crossAxisCount: 2,
              mainAxisSpacing: 10,
              crossAxisSpacing: 10,
              childAspectRatio: 1.22,
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              children: [for (final p in palettes) _Tile(onSelect: (o) => ThemeController.I.select(p.id, origin: o), on: mode == p.id, title: p.name, note: p.note, preview: _Swatch(p))],
            ),
          ]);
        },
      );
}

class _Swatch extends StatelessWidget {
  const _Swatch(this.p);
  final Palette p;
  @override
  Widget build(BuildContext context) => Container(
        color: p.bg,
        padding: const EdgeInsets.all(8),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisAlignment: MainAxisAlignment.center, children: [
          Container(
            height: 22,
            padding: const EdgeInsets.symmetric(horizontal: 6),
            decoration: BoxDecoration(color: p.surface, borderRadius: BorderRadius.circular(8), border: Border.all(color: p.line)),
            child: Row(children: [
              Container(width: 10, height: 10, decoration: BoxDecoration(color: p.primary, shape: BoxShape.circle)),
              const SizedBox(width: 5),
              Expanded(child: Container(height: 4, decoration: BoxDecoration(color: p.text.withValues(alpha: 0.25), borderRadius: BorderRadius.circular(3)))),
            ]),
          ),
          const SizedBox(height: 5),
          Row(children: [for (final c in [p.good, p.warn, p.bad, p.violet]) Container(width: 9, height: 9, margin: const EdgeInsets.only(right: 4), decoration: BoxDecoration(color: c, shape: BoxShape.circle))]),
        ]),
      );
}

class _Tile extends StatelessWidget {
  const _Tile({required this.onSelect, required this.on, required this.title, required this.note, required this.preview});
  final void Function(Offset) onSelect;
  final bool on;
  final String title, note;
  final Widget preview;

  @override
  Widget build(BuildContext context) {
    Offset pos = Offset.zero;
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTapDown: (d) => pos = d.globalPosition,
      onTap: () {
        tick();
        onSelect(pos);
      },
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 260),
        curve: Curves.easeOutCubic,
        decoration: BoxDecoration(color: C.surface, borderRadius: BorderRadius.circular(R.md), border: Border.all(color: on ? C.primary : C.line, width: on ? 2 : 1), boxShadow: C.shadow),
        clipBehavior: Clip.antiAlias,
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Expanded(child: preview),
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 8, 12, 10),
            child: Row(children: [
              Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(title, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13.5)), Text(note, maxLines: 1, overflow: TextOverflow.ellipsis, style: T.small.copyWith(fontSize: 11))])),
              AnimatedScale(scale: on ? 1 : 0, duration: const Duration(milliseconds: 300), curve: springy, child: Icon(Icons.check_circle_rounded, color: C.primary, size: 20)),
            ]),
          ),
        ]),
      ),
    );
  }
}

class _AutomationCard extends StatefulWidget {
  const _AutomationCard();
  @override
  State<_AutomationCard> createState() => _AutomationCardState();
}

class _AutomationCardState extends State<_AutomationCard> {
  final _r = Resource<Map<String, dynamic>>(() async => asMap(await Session.I.api.get('/automation/status')));

  @override
  void initState() {
    super.initState();
    _r.load();
  }

  @override
  void dispose() {
    _r.dispose();
    super.dispose();
  }

  Future<void> _put(Map<String, dynamic> patch) async {
    final r = await guarded(context, () => Session.I.api.put('/automation/settings', data: patch));
    if (r != null) _r.set(asMap(r));
  }

  Future<void> _pauseAll(bool v) async {
    final r = await guarded(context, () => Session.I.api.post(v ? '/automation/pause-all' : '/automation/resume-all'), ok: v ? 'Everything paused' : 'Automation resumed');
    if (r != null) _r.set(asMap(r));
  }

  @override
  Widget build(BuildContext context) => ListenableBuilder(
        listenable: _r,
        builder: (context, _) {
          final d = _r.data;
          if (d == null) return _r.error != null ? ErrorState(error: _r.error!, onRetry: _r.load) : const Busy();
          final pauses = asMap(d['pauses']);
          final limits = asMap(d['limits']);
          final mode = '${d['mode']}';
          return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            RowsCard(children: [
              ToggleRow(icon: Icons.pause_circle_rounded, title: 'Pause everything', sub: 'Emergency stop for every agent', value: d['paused_all'] == true, onChanged: _pauseAll),
            ]),
            const SizedBox(height: 12),
            GlassCard(
              radius: R.md,
              padding: const EdgeInsets.symmetric(vertical: 14),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Padding(padding: const EdgeInsets.symmetric(horizontal: 18), child: Text('MODE', style: T.label)),
                const SizedBox(height: 8),
                ChipRow(options: const ['conservative', 'balanced', 'autonomous'], labels: const {'conservative': 'Conservative', 'balanced': 'Balanced', 'autonomous': 'Autonomous'}, value: mode, onChanged: (v) => _put({'mode': v})),
                Padding(padding: const EdgeInsets.fromLTRB(18, 8, 18, 0), child: Text('Whatever the mode, applying and sending wait for your approval unless you turned on a standing approval on the web.', style: T.small)),
              ]),
            ),
            const SizedBox(height: 12),
            RowsCard(children: [
              for (final e in _capLabels.entries)
                ToggleRow(title: e.value.$1, sub: e.value.$2, value: pauses[e.key] != true, onChanged: (on) => _put({'pauses': {...pauses, e.key: !on}})),
            ]),
            const SizedBox(height: 12),
            GlassCard(
              radius: R.md,
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('DAILY LIMITS', style: T.label),
                const SizedBox(height: 10),
                _Stepper(label: 'Applications', value: (limits['daily_application_limit'] as num?)?.toInt() ?? 20, min: 1, max: 50, onChanged: (v) => _put({'limits': {...limits, 'daily_application_limit': v}})),
                _Stepper(label: 'Emails', value: (limits['daily_email_limit'] as num?)?.toInt() ?? 20, min: 1, max: 50, onChanged: (v) => _put({'limits': {...limits, 'daily_email_limit': v}})),
                _Stepper(label: 'Recruiter messages (max 10)', value: (limits['daily_recruiter_contact_limit'] as num?)?.toInt() ?? 10, min: 1, max: 10, onChanged: (v) => _put({'limits': {...limits, 'daily_recruiter_contact_limit': v}})),
                _Stepper(label: 'Minimum match %', value: (limits['min_match_score'] as num?)?.toInt() ?? 70, min: 40, max: 95, step: 5, onChanged: (v) => _put({'limits': {...limits, 'min_match_score': v}})),
              ]),
            ),
          ]);
        },
      );
}

class _Stepper extends StatelessWidget {
  const _Stepper({required this.label, required this.value, required this.min, required this.max, required this.onChanged, this.step = 1});
  final String label;
  final int value, min, max, step;
  final ValueChanged<int> onChanged;
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Row(children: [
          Expanded(child: Text(label)),
          _Btn(Icons.remove_rounded, value > min ? () => onChanged((value - step).clamp(min, max)) : null),
          SizedBox(width: 44, child: Center(child: Text('$value', style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16)))),
          _Btn(Icons.add_rounded, value < max ? () => onChanged((value + step).clamp(min, max)) : null),
        ]),
      );
}

class _Btn extends StatelessWidget {
  const _Btn(this.icon, this.onTap);
  final IconData icon;
  final VoidCallback? onTap;
  @override
  Widget build(BuildContext context) => Pressable(
        onTap: onTap,
        child: Container(width: 36, height: 36, decoration: BoxDecoration(shape: BoxShape.circle, color: C.surface2), child: Icon(icon, size: 20, color: onTap == null ? C.muted.withValues(alpha: 0.4) : C.text)),
      );
}
