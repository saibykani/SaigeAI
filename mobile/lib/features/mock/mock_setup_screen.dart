import 'package:material_ui/material_ui.dart';

import '../../core/api.dart';
import '../../core/motion.dart';
import '../../core/resource.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/kit.dart';
import '../../core/widgets/ui.dart';
import 'interview_room.dart';
import 'interviewer_face.dart';
import 'mock_report_screen.dart';

/// Set up a mock interview (role or saved job, type, difficulty, language) and see past sessions.
class MockSetupScreen extends StatefulWidget {
  const MockSetupScreen({super.key});
  @override
  State<MockSetupScreen> createState() => _MockSetupScreenState();
}

class _MockSetupScreenState extends State<MockSetupScreen> {
  final _role = TextEditingController();
  final _history = Resource<List<Map<String, dynamic>>>(() async => asList(await Session.I.api.get('/mock-interview/sessions')));
  final _jobs = Resource<List<Map<String, dynamic>>>(() async => asList(asMap(await Session.I.api.get('/jobs', query: {'limit': 20, 'sort': 'score'}))['items']));
  String _type = 'mixed';
  String _diff = 'medium';
  String _lang = 'en';
  String? _jobId;
  int _n = 8;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _history.load();
    _jobs.load();
  }

  @override
  void dispose() {
    _role.dispose();
    _history.dispose();
    _jobs.dispose();
    super.dispose();
  }

  Future<void> _start() async {
    if (_jobId == null && _role.text.trim().isEmpty) return toast(context, 'Type a role or pick a saved job.', error: true);
    FocusScope.of(context).unfocus();
    setState(() => _busy = true);
    try {
      final s = asMap(await Session.I.api.post('/mock-interview/sessions', data: {
        'role': _role.text.trim(),
        if (_jobId != null) 'job_id': _jobId,
        'interview_type': _type,
        'difficulty': _diff,
        'num_questions': _n,
        'language': _lang,
        'persona': 'priya',
      }));
      thump();
      if (!mounted) return;
      await pushDepth(context, (_) => InterviewRoom(session: s));
      _history.load();
    } on ApiException catch (e) {
      if (mounted) toast(context, e.message, error: true);
    }
    if (mounted) setState(() => _busy = false);
  }

  Future<void> _openPast(Map<String, dynamic> row) async {
    try {
      final d = asMap(await Session.I.api.get('/mock-interview/sessions/${row['id']}'));
      if (!mounted) return;
      if (d['report'] != null) {
        await pushDepth(context, (_) => MockReportScreen(report: asMap(d['report']), role: '${d['role']}'));
      } else {
        await pushDepth(context, (_) => InterviewRoom(session: d));
      }
      _history.load();
    } on ApiException catch (e) {
      if (mounted) toast(context, e.message, error: true);
    }
  }

  @override
  Widget build(BuildContext context) => FeatureScaffold(
        title: 'Mock interview',
        subtitle: 'Practise out loud with a voice interviewer',
        child: ListView(
          physics: const BouncingScrollPhysics(),
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 120),
          children: [
            Stagger(
              index: 0,
              child: GlassCard(
                child: Row(children: [
                  const InterviewerFace(mood: FaceMood.idle, size: 96),
                  const SizedBox(width: 14),
                  Expanded(child: Text('Priya asks questions from your real profile and the role. Answer by voice or text. Every answer is scored, and nothing leaves your account.', style: T.small)),
                ]),
              ),
            ),
            const SizedBox(height: 18),
            LabeledField(label: 'Role', controller: _role, hint: 'e.g. SDET, Data Analyst'),
            ListenableBuilder(
              listenable: _jobs,
              builder: (context, _) {
                final l = _jobs.data ?? const <Map<String, dynamic>>[];
                if (l.isEmpty) return const SizedBox.shrink();
                final labels = {for (final j in l) '${j['id']}': '${j['title']}'.length > 26 ? '${'${j['title']}'.substring(0, 26)}…' : '${j['title']}'};
                return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Padding(padding: EdgeInsets.fromLTRB(4, 18, 0, 8), child: Text('OR PRACTISE FOR A SAVED JOB', style: T.label)),
                  ChipRow(padding: 0, options: ['', ...labels.keys], labels: {'': 'None', ...labels}, value: _jobId ?? '', onChanged: (v) => setState(() => _jobId = v.isEmpty ? null : v)),
                ]);
              },
            ),
            const SizedBox(height: 18),
            Text('TYPE', style: T.label),
            const SizedBox(height: 8),
            ChipRow(padding: 0, options: const ['mixed', 'hr', 'technical', 'behavioural'], labels: const {'mixed': 'Mixed', 'hr': 'HR', 'technical': 'Technical', 'behavioural': 'Behavioural'}, value: _type, onChanged: (v) => setState(() => _type = v)),
            const SizedBox(height: 16),
            Text('DIFFICULTY', style: T.label),
            const SizedBox(height: 8),
            ChipRow(padding: 0, options: const ['easy', 'medium', 'hard'], labels: const {'easy': 'Easy', 'medium': 'Medium', 'hard': 'Hard'}, value: _diff, onChanged: (v) => setState(() => _diff = v)),
            const SizedBox(height: 16),
            Text('LANGUAGE', style: T.label),
            const SizedBox(height: 8),
            ChipRow(padding: 0, options: mockLocales.keys.toList(), labels: const {'en': 'English', 'hi': 'हिन्दी', 'te': 'తెలుగు', 'ta': 'தமிழ்', 'kn': 'ಕನ್ನಡ', 'ml': 'മലയാളം'}, value: _lang, onChanged: (v) => setState(() => _lang = v)),
            const SizedBox(height: 16),
            Row(children: [
              Expanded(child: Text('QUESTIONS', style: T.label)),
              Pressable(onTap: () => setState(() => _n = (_n - 1).clamp(5, 15)), child: Icon(Icons.remove_circle_outline_rounded, color: C.muted)),
              SizedBox(width: 50, child: Center(child: Text('$_n', style: T.h2))),
              Pressable(onTap: () => setState(() => _n = (_n + 1).clamp(5, 15)), child: Icon(Icons.add_circle_outline_rounded, color: C.muted)),
            ]),
            const SizedBox(height: 20),
            PrimaryButton(label: 'Start interview', icon: Icons.play_arrow_rounded, busy: _busy, onTap: _start),
            const SectionTitle('Past sessions'),
            ListenableBuilder(
              listenable: _history,
              builder: (context, _) {
                final l = _history.data;
                if (l == null) return _history.error != null ? ErrorState(error: _history.error!, onRetry: _history.load) : const Busy();
                if (l.isEmpty) return GlassCard(child: Text('Your finished interviews and scores will show up here.', style: T.small));
                return Column(children: [
                  for (final (i, s) in l.indexed)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 10),
                      child: Stagger(
                        index: i % 8,
                        child: GlassCard(
                          radius: R.md,
                          padding: const EdgeInsets.all(14),
                          onTap: () => _openPast(s),
                          child: Row(children: [
                            Expanded(
                              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                Text('${s['role']}', maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w600)),
                                Text('${prettyStatus('${s['interview_type']}')}  ·  ${s['questions']} questions  ·  ${timeAgo('${s['created_at']}')}', style: T.small),
                              ]),
                            ),
                            if (s['score'] != null) Text('${s['score']}', style: T.h1.copyWith(color: scoreColor(s['score'] as num?))) else Pill('In progress', color: C.warn),
                          ]),
                        ),
                      ),
                    ),
                ]);
              },
            ),
          ],
        ),
      );
}
