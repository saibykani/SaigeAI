import 'dart:async';

import 'package:flutter_tts/flutter_tts.dart';
import 'package:material_ui/material_ui.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:speech_to_text/speech_to_text.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/motion.dart';
import '../../core/resource.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/voice.dart';
import '../../core/widgets/dot_ring.dart';
import '../../core/widgets/forms.dart';
import '../../core/widgets/ui.dart';
import '../mock/mock_setup_screen.dart';

/// Interview day mode: live countdown, Join, and a brief built only from the user's own interview, saved job and profile.
class InterviewDayScreen extends StatefulWidget {
  const InterviewDayScreen({super.key, this.interviewId, this.emailId});
  final String? interviewId;
  final String? emailId;
  @override
  State<InterviewDayScreen> createState() => _InterviewDayScreenState();
}

class _InterviewDayScreenState extends State<InterviewDayScreen> with SingleTickerProviderStateMixin {
  late final Resource<Map<String, dynamic>> _brief = Resource(() async {
    final api = Session.I.api;
    if (widget.interviewId != null) return asMap(await api.get('/interviews/${widget.interviewId}/brief'));
    return asMap(await api.get('/interviews/brief', query: {'email_id': widget.emailId}));
  });
  late final AnimationController _pulse = AnimationController(vsync: this, duration: const Duration(milliseconds: 1400))..repeat(reverse: true);
  Timer? _timer;
  Set<int> _done = {};
  SharedPreferences? _prefs;

  String get _key => 'interview_day_checks_${widget.interviewId ?? widget.emailId}';

  @override
  void initState() {
    super.initState();
    _brief.load();
    _timer = Timer.periodic(const Duration(seconds: 1), (_) => mounted ? setState(() {}) : null);
    SharedPreferences.getInstance().then((p) {
      _prefs = p;
      if (mounted) setState(() => _done = (p.getStringList(_key) ?? const []).map(int.parse).toSet());
    }).catchError((_) {});
  }

  @override
  void dispose() {
    _timer?.cancel();
    _pulse.dispose();
    _brief.dispose();
    super.dispose();
  }

  void _toggle(int i) {
    tick();
    setState(() => _done.contains(i) ? _done.remove(i) : _done.add(i));
    _prefs?.setStringList(_key, _done.map((e) => '$e').toList());
  }

  Future<void> _join(String url) async {
    final u = Uri.tryParse(url);
    if (u != null) await launchUrl(u, mode: LaunchMode.externalApplication).catchError((_) => false);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        backgroundColor: C.bg,
        body: SafeArea(
          child: Stack(children: [
            ListenableBuilder(
              listenable: _brief,
              builder: (context, _) {
                final b = _brief.data;
                if (b == null) {
                  if (_brief.error != null) return ErrorState(error: _brief.error!, onRetry: _brief.load);
                  return const LoadingState();
                }
                return _body(b);
              },
            ),
            Positioned(left: 12, top: 8, child: Pressable(onTap: () => Navigator.of(context).maybePop(), child: Container(width: 46, height: 46, decoration: BoxDecoration(shape: BoxShape.circle, color: C.surface2, border: Border.all(color: C.line)), child: const Icon(Icons.arrow_back_rounded)))),
          ]),
        ),
      );

  Widget _body(Map<String, dynamic> b) {
    final at = DateTime.tryParse('${b['scheduled_at']}')?.toLocal();
    final url = '${b['meeting_url'] ?? ''}';
    final skills = (b['skills'] as List? ?? const []).map((e) => '$e').toList();
    final reqs = (b['requirements'] as List? ?? const []).map((e) => '$e').toList();
    final brush = (b['brush_up'] as List? ?? const []).map((e) => '$e').toList();
    final matching = asList(b['matching']);
    final questions = asList(b['questions']);
    final checklist = (b['checklist'] as List? ?? const []).map((e) => '$e').toList();
    var n = 0;
    Widget s(Widget w) => Padding(padding: const EdgeInsets.only(bottom: 14), child: Stagger(index: n++, child: w));
    return ListView(
      physics: const BouncingScrollPhysics(),
      padding: const EdgeInsets.fromLTRB(20, 64, 20, 48),
      children: [
        s(Text('Interview day', style: T.display)),
        s(_countdown(at, url)),
        s(GlassCard(
          radius: R.md,
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('COMPANY & ROLE', style: T.label),
            const SizedBox(height: 8),
            Text('${b['company'] ?? 'Interview'}', style: T.h1),
            if ('${b['role'] ?? ''}'.isNotEmpty) Text('${b['role']}', style: T.body),
            const SizedBox(height: 10),
            Wrap(spacing: 8, runSpacing: 8, children: [
              if (b['round'] != null) Pill('${b['round']}', color: C.primary, filled: true),
              if (at != null) Pill(_fmt(at), color: C.good, filled: true),
            ]),
          ]),
        )),
        if (b['has_job'] != true)
          s(GlassCard(radius: R.md, child: Text('No saved job matches this interview, so there is no job description to prep from. Save the job to unlock requirements, matching projects and tailored questions.', style: T.small))),
        if (skills.isNotEmpty || reqs.isNotEmpty)
          s(_section('What they want', Icons.track_changes_rounded, [
            if (skills.isNotEmpty) Wrap(spacing: 8, runSpacing: 8, children: [for (final k in skills) Pill(k, color: C.primary, filled: true)]),
            for (final r in reqs.take(5)) Padding(padding: const EdgeInsets.only(top: 8), child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [Padding(padding: const EdgeInsets.only(top: 7, right: 8), child: Container(width: 5, height: 5, decoration: BoxDecoration(color: C.muted, shape: BoxShape.circle))), Expanded(child: Text(r, style: T.small))])),
          ])),
        if (matching.isNotEmpty)
          s(_section('Your matching projects', Icons.work_outline_rounded, [
            for (final m in matching)
              Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: Container(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(color: C.surface2, borderRadius: BorderRadius.circular(R.sm), border: Border.all(color: C.line)),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text('${m['name']}', style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15)),
                    if ('${m['line'] ?? ''}'.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 4), child: Text('${m['line']}', style: T.small)),
                    const SizedBox(height: 8),
                    Wrap(spacing: 6, runSpacing: 6, children: [for (final k in (m['skills'] as List? ?? const [])) Pill('$k', color: C.good)]),
                  ]),
                ),
              ),
          ])),
        if (brush.isNotEmpty)
          s(_section('Brush up', Icons.menu_book_outlined, [
            Text('In the job description but not in your profile yet. Be ready to say how you would learn them.', style: T.small),
            const SizedBox(height: 10),
            Wrap(spacing: 8, runSpacing: 8, children: [for (final k in brush) Pill(k, color: C.warn, filled: true)]),
          ])),
        if (questions.isNotEmpty) ...[
          s(PrimaryButton(label: '5-minute warm-up', icon: Icons.record_voice_over_rounded, onTap: () => showSheet(context, (_) => _WarmUp(questions: questions.map((q) => '${q['text']}').take(3).toList())))),
          s(_section('Likely questions', Icons.help_outline_rounded, [
            for (final q in questions) _Question(q: q, onPractise: () => showSheet(context, (_) => _WarmUp(questions: ['${q['text']}']))),
          ])),
        ],
        if (b['job_id'] != null)
          s(PrimaryButton(label: 'Full mock interview', icon: Icons.mic_none_rounded, ghost: true, onTap: () => pushDepth(context, (_) => const MockSetupScreen()))),
        s(_section('Checklist', Icons.checklist_rounded, [
          for (final (i, t) in checklist.indexed)
            Pressable(
              onTap: () => _toggle(i),
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 8),
                child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  AnimatedContainer(
                    duration: const Duration(milliseconds: 200),
                    width: 24,
                    height: 24,
                    decoration: BoxDecoration(shape: BoxShape.circle, color: _done.contains(i) ? C.good : Colors.transparent, border: Border.all(color: _done.contains(i) ? C.good : C.line, width: 1.6)),
                    child: _done.contains(i) ? Icon(Icons.check_rounded, size: 16, color: C.onPrimary) : null,
                  ),
                  const SizedBox(width: 12),
                  Expanded(child: Text(t, style: TextStyle(fontSize: 14.5, height: 1.35, color: _done.contains(i) ? C.muted : C.text, decoration: _done.contains(i) ? TextDecoration.lineThrough : null))),
                ]),
              ),
            ),
        ])),
      ],
    );
  }

  Widget _section(String title, IconData icon, List<Widget> children) => GlassCard(
        radius: R.md,
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [Icon(icon, size: 20, color: C.primary), const SizedBox(width: 8), Text(title, style: T.h2)]),
          const SizedBox(height: 12),
          ...children,
        ]),
      );

  Widget _countdown(DateTime? at, String url) {
    if (at == null) {
      return GlassCard(radius: R.md, child: Text('The interview time was not found in the invite. Open the email to confirm it.', style: T.small));
    }
    final diff = at.difference(DateTime.now());
    final now = diff.inMinutes <= 5;
    final over = diff.inMinutes < -90;
    final parts = [(diff.inDays, 'DAYS'), (diff.inHours % 24, 'HOURS'), (diff.inMinutes % 60, 'MIN')];
    return GlassCard(
      radius: R.lg,
      padding: const EdgeInsets.fromLTRB(20, 22, 20, 20),
      child: Column(children: [
        if (over)
          Text('This interview has passed', style: T.h2)
        else if (now)
          AnimatedBuilder(animation: _pulse, builder: (_, _) => Text('Starting now', style: T.h1.copyWith(color: Color.lerp(C.good, C.text, _pulse.value * 0.4))))
        else
          Row(mainAxisAlignment: MainAxisAlignment.spaceEvenly, children: [
            for (final (v, l) in parts) Column(children: [Text(v.toString().padLeft(2, '0'), style: const TextStyle(fontSize: 46, fontWeight: FontWeight.w700, letterSpacing: -1.5, fontFeatures: [FontFeature.tabularFigures()])), Text(l, style: T.label)]),
          ]),
        if (url.isNotEmpty && !over) ...[
          const SizedBox(height: 18),
          AnimatedBuilder(
            animation: _pulse,
            builder: (_, child) => DecoratedBox(
              decoration: BoxDecoration(borderRadius: BorderRadius.circular(99), boxShadow: now ? [BoxShadow(color: C.good.withValues(alpha: 0.25 + 0.3 * _pulse.value), blurRadius: 12 + 16 * _pulse.value)] : null),
              child: child,
            ),
            child: PrimaryButton(label: 'Join interview', icon: Icons.videocam_rounded, onTap: () => _join(url)),
          ),
        ],
      ]),
    );
  }
}

String _fmt(DateTime d) {
  const m = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  final h = d.hour % 12 == 0 ? 12 : d.hour % 12;
  return '${d.day} ${m[d.month - 1]}, $h:${d.minute.toString().padLeft(2, '0')} ${d.hour < 12 ? 'AM' : 'PM'}';
}

class _Question extends StatefulWidget {
  const _Question({required this.q, required this.onPractise});
  final Map<String, dynamic> q;
  final VoidCallback onPractise;
  @override
  State<_Question> createState() => _QuestionState();
}

class _QuestionState extends State<_Question> {
  bool _open = false;
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: Pressable(
          onTap: () {
            tick();
            setState(() => _open = !_open);
          },
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 250),
            curve: Curves.easeOutCubic,
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(color: C.surface2, borderRadius: BorderRadius.circular(R.sm), border: Border.all(color: _open ? C.primary.withValues(alpha: 0.5) : C.line)),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Expanded(child: Text('${widget.q['text']}', style: const TextStyle(fontSize: 14.5, height: 1.35, fontWeight: FontWeight.w500))),
                Icon(_open ? Icons.expand_less_rounded : Icons.expand_more_rounded, color: C.muted),
              ]),
              AnimatedSize(
                duration: const Duration(milliseconds: 250),
                curve: Curves.easeOutCubic,
                alignment: Alignment.topCenter,
                child: !_open
                    ? const SizedBox(width: double.infinity)
                    : Padding(
                        padding: const EdgeInsets.only(top: 12),
                        child: Row(children: [
                          Pill(prettyStatus('${widget.q['kind']}'), color: C.muted),
                          if (widget.q['skill'] != null) ...[const SizedBox(width: 6), Pill('${widget.q['skill']}', color: C.primary)],
                          const Spacer(),
                          Pressable(onTap: widget.onPractise, child: Container(padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 9), decoration: BoxDecoration(color: C.primarySoft, borderRadius: BorderRadius.circular(99)), child: Row(mainAxisSize: MainAxisSize.min, children: [Icon(Icons.mic_rounded, size: 16, color: C.primary), const SizedBox(width: 6), Text('Practise aloud', style: TextStyle(color: C.primary, fontWeight: FontWeight.w600, fontSize: 13))]))),
                        ]),
                      ),
              ),
            ]),
          ),
        ),
      );
}

enum _Step { speaking, listening, review }

/// Speaks each question, listens to the spoken answer and shows the transcript. No scoring: just practice and encouragement.
class _WarmUp extends StatefulWidget {
  const _WarmUp({required this.questions});
  final List<String> questions;
  @override
  State<_WarmUp> createState() => _WarmUpState();
}

class _WarmUpState extends State<_WarmUp> {
  final _tts = FlutterTts();
  final _stt = SpeechToText();
  int _i = 0;
  _Step _step = _Step.speaking;
  String _heard = '';
  bool _sttReady = false;
  bool _dead = false;
  int _epoch = 0;

  @override
  void initState() {
    super.initState();
    _ask();
  }

  @override
  void dispose() {
    _dead = true;
    _epoch++;
    _tts.stop();
    _stt.cancel();
    super.dispose();
  }

  Future<void> _ask() async {
    final my = ++_epoch;
    setState(() {
      _step = _Step.speaking;
      _heard = '';
    });
    try {
      await useHumanVoice(_tts, 'en-IN');
      await _tts.awaitSpeakCompletion(true);
      await _tts.speak(widget.questions[_i]);
    } catch (_) {/* no TTS: the question is on screen */}
    if (_dead || my != _epoch) return;
    await _listen();
  }

  Future<void> _listen() async {
    if (!_sttReady) {
      try {
        _sttReady = await _stt.initialize(onStatus: (s) {
          if ((s == 'done' || s == 'notListening') && mounted && _step == _Step.listening) setState(() => _step = _Step.review);
        }, onError: (_) {
          if (mounted) setState(() => _step = _Step.review);
        });
      } catch (_) {
        _sttReady = false;
      }
    }
    if (!_sttReady) {
      if (mounted) {
        toast(context, 'Speech recognition is not available. Answer aloud and tap Next.', error: true);
        setState(() => _step = _Step.review);
      }
      return;
    }
    if (!mounted) return;
    setState(() => _step = _Step.listening);
    await _stt.listen(
      listenOptions: SpeechListenOptions(partialResults: true, cancelOnError: true, listenMode: ListenMode.dictation, pauseFor: const Duration(seconds: 4)),
      onResult: (r) {
        if (mounted) setState(() => _heard = r.recognizedWords);
      },
    );
  }

  Future<void> _stop() async {
    await _stt.stop();
    if (mounted) setState(() => _step = _Step.review);
  }

  String get _cheer {
    final w = _heard.trim().isEmpty ? 0 : _heard.trim().split(RegExp(r'\s+')).length;
    if (w == 0) return 'No answer heard. Try again, even a rough spoken draft helps.';
    if (w < 25) return 'Good start. Try adding one concrete example from your own work.';
    if (w < 120) return 'Nice, that is a solid length. Check you covered the situation, what you did and the result.';
    return 'Great detail. In the real interview, aim to keep it to about two minutes.';
  }

  @override
  Widget build(BuildContext context) {
    final last = _i >= widget.questions.length - 1;
    return Padding(
      padding: const EdgeInsets.fromLTRB(22, 8, 22, 28),
      child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('QUESTION ${_i + 1} OF ${widget.questions.length}', style: T.label),
        const SizedBox(height: 10),
        Text(widget.questions[_i], style: T.h2),
        const SizedBox(height: 18),
        Center(child: DotRing(size: 64, dots: 20, progress: _step == _Step.review ? 1 : null, color: _step == _Step.listening ? C.good : C.primary)),
        const SizedBox(height: 10),
        Center(child: Text(switch (_step) { _Step.speaking => 'Listen to the question', _Step.listening => 'Listening, answer out loud', _Step.review => 'Your answer' }, style: T.small)),
        if (_heard.isNotEmpty) ...[
          const SizedBox(height: 14),
          Container(width: double.infinity, padding: const EdgeInsets.all(14), decoration: BoxDecoration(color: C.surface2, borderRadius: BorderRadius.circular(R.sm), border: Border.all(color: C.line)), child: Text(_heard, style: T.body)),
        ],
        if (_step == _Step.review) ...[const SizedBox(height: 12), Text(_cheer, style: T.small)],
        const SizedBox(height: 18),
        if (_step == _Step.listening) PrimaryButton(label: 'Done answering', icon: Icons.stop_rounded, onTap: _stop),
        if (_step == _Step.speaking) PrimaryButton(label: 'Skip to answer', ghost: true, onTap: () async {
          _epoch++;
          await _tts.stop();
          await _listen();
        }),
        if (_step == _Step.review)
          Row(children: [
            Expanded(child: PrimaryButton(label: 'Try again', ghost: true, onTap: _ask)),
            const SizedBox(width: 10),
            Expanded(
              child: PrimaryButton(
                label: last ? 'Finish' : 'Next',
                onTap: () {
                  if (last) return Navigator.of(context).pop();
                  setState(() => _i++);
                  _ask();
                },
              ),
            ),
          ]),
      ]),
    );
  }
}
