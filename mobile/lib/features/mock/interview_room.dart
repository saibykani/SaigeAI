import 'dart:async';

import '../../core/voice.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:material_ui/material_ui.dart';
import 'package:speech_to_text/speech_to_text.dart';

import '../../core/api.dart';
import '../../core/motion.dart';
import '../../core/resource.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/dot_ring.dart';
import '../../core/widgets/kit.dart';
import '../../core/widgets/ui.dart';
import 'interviewer_face.dart';
import 'mock_report_screen.dart';

const mockLocales = {'en': 'en-IN', 'hi': 'hi-IN', 'te': 'te-IN', 'ta': 'ta-IN', 'kn': 'kn-IN', 'ml': 'ml-IN'};

enum _Phase { asking, answering, scoring, feedback, finishing }

/// The interview room: the interviewer asks out loud, you answer by voice or text, each answer is scored.
class InterviewRoom extends StatefulWidget {
  const InterviewRoom({super.key, required this.session});
  final Map<String, dynamic> session;
  @override
  State<InterviewRoom> createState() => _InterviewRoomState();
}

class _InterviewRoomState extends State<InterviewRoom> {
  final _tts = FlutterTts();
  final _stt = SpeechToText();
  final _text = TextEditingController();
  late final List<Map<String, dynamic>> _qs = asList(widget.session['questions']);
  late final String _lang = '${widget.session['language'] ?? 'en'}';
  int _i = 0;
  _Phase _phase = _Phase.asking;
  FaceMood _mood = FaceMood.idle;
  bool _sttReady = false;
  bool _listening = false;
  bool _voiceOn = true;
  double _level = 0;
  Map<String, dynamic>? _fb;
  DateTime _answerStart = DateTime.now();
  Timer? _fakeTalk;
  int _epoch = 0; // invalidates stale speech callbacks

  @override
  void initState() {
    super.initState();
    _tts.setCompletionHandler(_spoken);
    _tts.setCancelHandler(() {});
    _tts.setErrorHandler((_) => _spoken());
    Future<void>.delayed(const Duration(milliseconds: 600), _ask);
  }

  @override
  void dispose() {
    _fakeTalk?.cancel();
    _tts.stop();
    _stt.cancel();
    _text.dispose();
    super.dispose();
  }

  String get _name => '${widget.session['persona'] ?? 'priya'}'.isEmpty ? 'Priya' : '${widget.session['persona']}'[0].toUpperCase() + '${widget.session['persona']}'.substring(1);

  void _spoken() {
    if (!mounted || _phase != _Phase.asking) return;
    _fakeTalk?.cancel();
    setState(() {
      _phase = _Phase.answering;
      _mood = FaceMood.idle;
      _answerStart = DateTime.now();
    });
    tick();
  }

  Future<void> _ask() async {
    if (!mounted) return;
    final q = '${_qs[_i]['text']}';
    setState(() {
      _phase = _Phase.asking;
      _mood = FaceMood.speaking;
      _fb = null;
      _text.clear();
    });
    final my = ++_epoch;
    if (!_voiceOn) {
      _fakeTalk = Timer(Duration(milliseconds: (q.length * 25).clamp(800, 3000)), () => my == _epoch ? _spoken() : null);
      return;
    }
    try {
      await _tts.stop();
      await useHumanVoice(_tts, mockLocales[_lang] ?? 'en-IN');
      await _tts.speak(q);
    } catch (_) {
      // No TTS engine: keep the mouth moving for a plausible reading time, then hand over.
      _fakeTalk = Timer(Duration(milliseconds: (q.length * 55).clamp(1500, 9000)), () => my == _epoch ? _spoken() : null);
    }
  }

  Future<void> _skipSpeech() async {
    _epoch++;
    await _tts.stop();
    _spoken();
  }

  Future<void> _mic() async {
    tap();
    if (_listening) {
      await _stt.stop();
      return;
    }
    await _tts.stop();
    if (_phase == _Phase.asking) _spoken();
    if (!_sttReady) {
      try {
        _sttReady = await _stt.initialize(onStatus: (s) {
          if ((s == 'done' || s == 'notListening') && mounted) {
            setState(() {
              _listening = false;
              _mood = FaceMood.idle;
              _level = 0;
            });
          }
        }, onError: (_) {
          if (mounted) setState(() => _listening = false);
        });
      } catch (_) {
        _sttReady = false;
      }
      if (!_sttReady) {
        if (mounted) toast(context, 'Speech recognition is not available. Type your answer instead.', error: true);
        return;
      }
    }
    final base = _text.text.trim();
    setState(() {
      _listening = true;
      _mood = FaceMood.listening;
    });
    await _stt.listen(
      onSoundLevelChange: (l) {
        if (mounted) setState(() => _level = ((l + 2) / 12).clamp(0.0, 1.0));
      },
      listenOptions: SpeechListenOptions(partialResults: true, cancelOnError: true, listenMode: ListenMode.dictation, localeId: (mockLocales[_lang] ?? 'en-IN').replaceAll('-', '_'), pauseFor: const Duration(seconds: 4)),
      onResult: (r) {
        _text.text = base.isEmpty ? r.recognizedWords : '$base ${r.recognizedWords}';
        _text.selection = TextSelection.collapsed(offset: _text.text.length);
      },
    );
  }

  Future<void> _submit({bool skip = false}) async {
    if (_listening) await _stt.stop();
    if (!mounted) return;
    final body = _text.text.trim();
    if (!skip && body.length < 3) return toast(context, 'Say or type your answer first, or skip.', error: true);
    FocusScope.of(context).unfocus();
    setState(() {
      _phase = _Phase.scoring;
      _mood = FaceMood.thinking;
    });
    try {
      final r = asMap(await Session.I.api.post('/mock-interview/sessions/${widget.session['id']}/answer', data: {
        'index': _i,
        'text': skip ? '' : body,
        'duration_s': DateTime.now().difference(_answerStart).inSeconds,
        'skipped': skip,
      }));
      thump();
      if (mounted) {
        setState(() {
          _fb = r;
          _phase = _Phase.feedback;
          _mood = FaceMood.idle;
        });
      }
    } on ApiException catch (e) {
      if (mounted) {
        setState(() {
          _phase = _Phase.answering;
          _mood = FaceMood.idle;
        });
        toast(context, e.message, error: true);
      }
    }
  }

  Future<void> _next() async {
    if (_i + 1 < _qs.length) {
      setState(() => _i++);
      _ask();
      return;
    }
    setState(() {
      _phase = _Phase.finishing;
      _mood = FaceMood.thinking;
    });
    try {
      final rep = asMap(await Session.I.api.post('/mock-interview/sessions/${widget.session['id']}/finish'));
      success();
      if (!mounted) return;
      await Navigator.of(context).pushReplacement(DepthRoute<void>(builder: (_) => MockReportScreen(report: rep, role: '${widget.session['role']}')));
    } on ApiException catch (e) {
      if (mounted) {
        setState(() => _phase = _Phase.feedback);
        toast(context, e.message, error: true);
      }
    }
  }

  Future<bool> _confirmLeave() async {
    final leave = await showModalBottomSheet<bool>(
      context: context,
      backgroundColor: C.surface,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(R.lg))),
      builder: (context) => Padding(
        padding: const EdgeInsets.all(24),
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text('Leave the interview?', style: T.h2),
          const SizedBox(height: 6),
          Text('Your answers so far are saved. You can start another session any time.', style: T.small),
          const SizedBox(height: 18),
          PrimaryButton(label: 'Keep going', onTap: () => Navigator.pop(context, false)),
          const SizedBox(height: 8),
          PrimaryButton(label: 'Leave', ghost: true, onTap: () => Navigator.pop(context, true)),
        ]),
      ),
    );
    return leave == true;
  }

  @override
  Widget build(BuildContext context) {
    final q = _qs[_i];
    final busy = _phase == _Phase.scoring || _phase == _Phase.finishing;
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) async {
        if (didPop) return;
        final nav = Navigator.of(context);
        if (await _confirmLeave()) nav.pop();
      },
      child: Scaffold(
        backgroundColor: C.bg,
        body: SafeArea(
          child: Column(children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
              child: Row(children: [
                Pressable(
                  onTap: () async {
                    final nav = Navigator.of(context);
                    if (await _confirmLeave()) nav.pop();
                  },
                  child: Container(width: 44, height: 44, decoration: BoxDecoration(shape: BoxShape.circle, color: C.surface2, border: Border.all(color: C.line)), child: const Icon(Icons.close_rounded, size: 20)),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text('Question ${_i + 1} of ${_qs.length}', style: const TextStyle(fontWeight: FontWeight.w600)),
                    const SizedBox(height: 6),
                    BarFill(value: (_i + (_phase == _Phase.feedback ? 1 : 0)) / _qs.length, height: 6),
                  ]),
                ),
                const SizedBox(width: 14),
                Pressable(
                  onTap: () {
                    setState(() => _voiceOn = !_voiceOn);
                    if (!_voiceOn) _tts.stop();
                  },
                  child: Container(width: 44, height: 44, decoration: BoxDecoration(shape: BoxShape.circle, color: C.surface2, border: Border.all(color: C.line)), child: Icon(_voiceOn ? Icons.volume_up_rounded : Icons.volume_off_rounded, size: 20, color: _voiceOn ? C.text : C.muted)),
                ),
              ]),
            ),
            Expanded(
              child: ListView(
                physics: const BouncingScrollPhysics(),
                padding: const EdgeInsets.fromLTRB(20, 8, 20, 30),
                children: [
                  Center(child: InterviewerFace(mood: _mood, size: 210, level: _level)),
                  Center(
                    child: Text(
                      switch (_mood) { FaceMood.speaking => '$_name is asking', FaceMood.listening => 'Listening to you', FaceMood.thinking => 'Thinking about your answer', FaceMood.idle => _phase == _Phase.feedback ? 'Here is my feedback' : 'Your turn' },
                      style: T.small,
                    ),
                  ),
                  const SizedBox(height: 14),
                  AnimatedSwitcher(
                    duration: const Duration(milliseconds: 400),
                    switchInCurve: Curves.easeOutCubic,
                    transitionBuilder: (c, a) => FadeTransition(opacity: a, child: SlideTransition(position: Tween(begin: const Offset(0, 0.08), end: Offset.zero).animate(a), child: c)),
                    child: GlassCard(
                      key: ValueKey(_i),
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Pill(prettyStatus('${q['kind']}'), color: C.primary, filled: true),
                        const SizedBox(height: 10),
                        Text('${q['text']}', style: T.h2.copyWith(height: 1.3)),
                      ]),
                    ),
                  ),
                  const SizedBox(height: 16),
                  if (_phase == _Phase.asking)
                    Center(child: Pressable(onTap: _skipSpeech, child: Padding(padding: EdgeInsets.all(10), child: Text('Skip the voice and answer now', style: TextStyle(color: C.primary, fontWeight: FontWeight.w600)))))
                  else if (_phase == _Phase.answering || busy) ..._answerArea(busy)
                  else if (_fb != null) ..._feedback(_fb!),
                ],
              ),
            ),
          ]),
        ),
      ),
    );
  }

  List<Widget> _answerArea(bool busy) => [
        if (busy)
          Padding(padding: const EdgeInsets.only(top: 20), child: Center(child: Column(children: [const DotRing(size: 56, dots: 22), const SizedBox(height: 12), Text(_phase == _Phase.finishing ? 'Building your report' : 'Scoring your answer', style: T.small)])))
        else ...[
          TextField(controller: _text, minLines: 3, maxLines: 7, decoration: const InputDecoration(hintText: 'Speak with the mic, or type your answer. Use real examples: situation, task, action, result.')),
          const SizedBox(height: 14),
          Row(children: [
            Pressable(
              onTap: _mic,
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 200),
                width: 64,
                height: 64,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: _listening ? C.good : C.surface2,
                  border: Border.all(color: _listening ? C.good : C.line),
                  boxShadow: _listening ? [BoxShadow(color: C.good.withValues(alpha: 0.35 + _level * 0.3), blurRadius: 18 + _level * 26, spreadRadius: _level * 6)] : null,
                ),
                child: Icon(_listening ? Icons.stop_rounded : Icons.mic_rounded, color: _listening ? Colors.white : C.text, size: 28),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(child: PrimaryButton(label: 'Submit answer', icon: Icons.arrow_upward_rounded, onTap: _submit)),
          ]),
          const SizedBox(height: 6),
          Center(child: Pressable(onTap: () => _submit(skip: true), child: Padding(padding: EdgeInsets.all(12), child: Text('Skip this question', style: T.small)))),
        ],
      ];

  List<Widget> _feedback(Map<String, dynamic> f) {
    final score = (f['score'] as num?) ?? 0;
    final fb = (f['feedback'] as List?)?.map((e) => '$e').toList() ?? const <String>[];
    final bd = asMap(f['breakdown']);
    final outline = (f['outline'] as List?)?.map((e) => '$e').toList() ?? const <String>[];
    const labels = {'relevance': 'On the question', 'structure': 'STAR structure', 'specifics': 'Specifics', 'length': 'Length', 'fluency': 'Fluency'};
    return [
      Stagger(
        index: 0,
        child: GlassCard(
          child: Row(children: [
            ScoreRing(score: score, size: 96, label: 'SCORE'),
            const SizedBox(width: 16),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                for (final e in bd.entries.where((e) => labels.containsKey(e.key)))
                  Padding(
                    padding: const EdgeInsets.only(bottom: 7),
                    child: Row(children: [
                      SizedBox(width: 96, child: Text(labels[e.key]!, style: T.small)),
                      Expanded(child: BarFill(value: ((e.value as num?) ?? 0) / 100, color: scoreColor(e.value as num?), height: 6)),
                    ]),
                  ),
              ]),
            ),
          ]),
        ),
      ),
      if (fb.isNotEmpty) ...[
        const SectionTitle('Feedback'),
        for (final (i, t) in fb.indexed) Stagger(index: i, child: Dot(t, C.warn)),
      ],
      if (outline.isNotEmpty) ...[
        const SectionTitle('A strong answer from your own facts'),
        for (final (i, t) in outline.indexed) Stagger(index: i, child: Dot(t, C.good)),
      ],
      const SizedBox(height: 14),
      PrimaryButton(label: _i + 1 < _qs.length ? 'Next question' : 'Finish and see report', icon: _i + 1 < _qs.length ? Icons.arrow_forward_rounded : Icons.flag_rounded, onTap: _next),
    ];
  }
}
