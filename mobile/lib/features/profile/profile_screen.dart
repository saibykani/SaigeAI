import 'package:dio/dio.dart';
import 'package:file_picker/file_picker.dart';
import 'package:material_ui/material_ui.dart';

import '../../core/api.dart';
import '../../core/config.dart';
import '../../core/motion.dart';
import '../../core/resource.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/confetti.dart';
import '../../core/widgets/dot_ring.dart';
import '../../core/widgets/scan_loader.dart';
import '../../core/widgets/ui.dart';
import '../more/more_hub.dart';
import '../settings/settings_screen.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});
  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  final _setup = Resource<Map<String, dynamic>>(() async => asMap(await Session.I.api.get('/profile/setup-status')));
  final _resumes = Resource<List<Map<String, dynamic>>>(() async => asList(await Session.I.api.get('/resumes')));
  bool _scanning = false;
  String _scanLabel = 'Reading your resume';

  @override
  void initState() {
    super.initState();
    _setup.load();
    _resumes.load();
  }

  @override
  void dispose() {
    _setup.dispose();
    _resumes.dispose();
    super.dispose();
  }

  Future<void> _refresh() => Future.wait([_setup.load(), _resumes.load()]);

  Future<void> _upload() async {
    List<PlatformFile> picked;
    try {
      picked = await FilePicker.pickFiles(type: FileType.custom, allowedExtensions: ['pdf', 'docx', 'txt']);
    } catch (_) {
      return;
    }
    if (picked.isEmpty || picked.first.path == null) return;
    final f = picked.first;
    setState(() {
      _scanning = true;
      _scanLabel = 'Reading your resume';
    });
    final started = DateTime.now();
    try {
      final name = f.name.replaceAll(RegExp(r'\.[^.]+$'), '');
      final form = FormData.fromMap({'file': await MultipartFile.fromFile(f.path!, filename: f.name), 'name': name, 'kind': 'Master Resume'});
      final r = asMap(await Session.I.api.request('POST', '/resumes', data: form));
      if (mounted) setState(() => _scanLabel = 'Adding verified facts to your profile');
      final imp = asMap(await Session.I.api.post('/resumes/${r['id']}/import-to-profile'));
      // Let the laser finish a pass so the moment lands even on fast uploads.
      final left = const Duration(milliseconds: 2300) - DateTime.now().difference(started);
      if (!left.isNegative) await Future<void>.delayed(left);
      if (mounted) {
        setState(() => _scanning = false);
        Confetti.burst(context);
        toast(context, 'Imported ${(imp['applied'] as List?)?.length ?? 0} profile fields. Unknown fields stay unknown.');
      }
      await _refresh();
    } on ApiException catch (e) {
      if (mounted) {
        setState(() => _scanning = false);
        toast(context, e.message, error: true);
      }
    } catch (_) {
      if (mounted) {
        setState(() => _scanning = false);
        toast(context, 'Upload failed. Check the file and try again.', error: true);
      }
    }
  }

  Future<void> _server() async {
    final c = TextEditingController(text: AppConfig.baseUrl);
    final v = await showModalBottomSheet<String>(
      context: context,
      isScrollControlled: true,
      backgroundColor: C.surface,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(R.lg))),
      builder: (context) => Padding(
        padding: EdgeInsets.fromLTRB(20, 24, 20, 24 + MediaQuery.viewInsetsOf(context).bottom),
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text('Server', style: T.h2),
          const SizedBox(height: 6),
          Text('Use the web host with /api so sign-in cookies stay first-party.', style: T.small),
          const SizedBox(height: 14),
          TextField(controller: c, keyboardType: TextInputType.url),
          const SizedBox(height: 14),
          PrimaryButton(label: 'Save', onTap: () => Navigator.pop(context, c.text)),
          const SizedBox(height: 8),
          PrimaryButton(label: 'Reset to default', ghost: true, onTap: () => Navigator.pop(context, AppConfig.defaultBaseUrl)),
        ]),
      ),
    );
    if (v != null) {
      await AppConfig.setBaseUrl(v);
      Session.I.api.baseUrl = AppConfig.baseUrl;
      if (mounted) toast(context, 'Server set to ${AppConfig.baseUrl}');
    }
  }

  @override
  Widget build(BuildContext context) {
    final u = Session.I.user;
    return SafeArea(
      bottom: false,
      child: Stack(children: [
        LogoRefreshView(onRefresh: _refresh, slivers: [
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(20, 12, 20, 0),
            sliver: SliverList.list(children: [
              Stagger(index: 0, child: Text('Profile', style: T.display)),
              const SizedBox(height: 18),
              Stagger(
                index: 1,
                child: GlassCard(
                  child: Row(children: [
                    ListenableBuilder(
                      listenable: _setup,
                      builder: (context, _) {
                        final comp = ((_setup.data?['completeness'] as num?) ?? 0).toDouble();
                        return DotRing(size: 108, dots: 34, progress: comp / 100, child: Column(mainAxisSize: MainAxisSize.min, children: [CountUp(value: comp, suffix: '%', style: T.h2), Text('DONE', style: T.label)]));
                      },
                    ),
                    const SizedBox(width: 18),
                    Expanded(
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Text('${u['name'] ?? ''}', style: T.h2, maxLines: 1, overflow: TextOverflow.ellipsis),
                        Text('${u['email'] ?? ''}', style: T.small, maxLines: 1, overflow: TextOverflow.ellipsis),
                        const SizedBox(height: 10),
                        Pill(Session.I.isRecruiter ? 'Recruiter' : 'Job seeker', color: C.primary, filled: true),
                      ]),
                    ),
                  ]),
                ),
              ),
              const SizedBox(height: 14),
              Stagger(
                index: 2,
                child: GlassCard(
                  onTap: () => pushDepth(context, (_) => const MoreHub()),
                  border: C.primary.withValues(alpha: 0.5),
                  child: Row(children: [
                    Icon(Icons.apps_rounded, color: C.primary, size: 30),
                    SizedBox(width: 14),
                    Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text('Everything in Saige', style: T.h2), Text('ATS coach, resume health, job search, inbox, goals, learning, mock interview', style: T.small)])),
                    Icon(Icons.chevron_right_rounded, color: C.muted),
                  ]),
                ),
              ),
              SectionTitle('Resumes', trailing: Pressable(onTap: _upload, child: Pill('Upload', color: C.primary, filled: true))),
              ListenableBuilder(
                listenable: _resumes,
                builder: (context, _) {
                  final list = _resumes.data;
                  if (list == null) return _resumes.error != null ? ErrorState(error: _resumes.error!, onRetry: _resumes.load) : Padding(padding: EdgeInsets.all(30), child: Center(child: DotRing(size: 40)));
                  if (list.isEmpty) return GlassCard(onTap: _upload, child: Row(children: [Icon(Icons.upload_file_rounded, color: C.primary), SizedBox(width: 12), Expanded(child: Text('Upload your resume (PDF, DOCX or TXT). Saige reads it and fills your profile with only what is in the file.', style: T.small))]));
                  return Column(children: [
                    for (final (i, r) in list.indexed)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 10),
                        child: Stagger(
                          index: i,
                          child: GlassCard(
                            radius: R.md,
                            padding: const EdgeInsets.all(14),
                            child: Row(children: [
                              Icon(Icons.description_outlined, color: C.muted),
                              const SizedBox(width: 12),
                              Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text('${r['name']}', maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w600)), Text('${r['kind']}  ·  v${r['version_count'] ?? 1}  ·  ${timeAgo('${r['updated_at']}')}', style: T.small)])),
                            ]),
                          ),
                        ),
                      ),
                  ]);
                },
              ),
              const SectionTitle('Settings'),
              GlassCard(
                padding: EdgeInsets.zero,
                child: Column(children: [
                  _Row(icon: Icons.tune_rounded, title: 'Settings', sub: 'Theme, language, automation, privacy', onTap: () => pushDepth(context, (_) => const SettingsScreen())),
                  Divider(height: 1, color: C.line),
                  _Row(icon: Icons.dns_outlined, title: 'Server', sub: AppConfig.baseUrl, onTap: _server),
                  Divider(height: 1, color: C.line),
                  _Row(icon: Icons.privacy_tip_outlined, title: 'Truth guard', sub: 'Saige never invents skills, titles or numbers. Unknown stays unknown.'),
                  Divider(height: 1, color: C.line),
                  _Row(icon: Icons.logout_rounded, title: 'Sign out', color: C.bad, onTap: () async {
                    thump();
                    await Session.I.logout();
                  }),
                ]),
              ),
              const SizedBox(height: 16),
              Center(child: Text('Saige AI 1.0  ·  Google sign-in coming soon', style: T.small)),
            ]),
          ),
        ]),
        if (_scanning)
          Positioned.fill(
            child: TweenAnimationBuilder<double>(
              tween: Tween(begin: 0, end: 1),
              duration: const Duration(milliseconds: 300),
              builder: (context, v, child) => Opacity(opacity: v, child: child),
              child: ColoredBox(color: C.bg.withValues(alpha: 0.94), child: Center(child: ScanLoader(label: _scanLabel))),
            ),
          ),
      ]),
    );
  }
}

class _Row extends StatelessWidget {
  const _Row({required this.icon, required this.title, this.sub, this.onTap, this.color});
  final IconData icon;
  final String title;
  final String? sub;
  final VoidCallback? onTap;
  final Color? color;
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
            if (onTap != null && color == null) Icon(Icons.chevron_right_rounded, color: C.muted),
          ]),
        ),
      );
}
