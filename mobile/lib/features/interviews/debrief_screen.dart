import 'package:material_ui/material_ui.dart';
import 'package:speech_to_text/speech_to_text.dart';

import '../../core/api.dart';
import '../../core/resource.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/forms.dart';
import '../../core/widgets/ui.dart';

/// Right after an interview: say or type what happened; Saige returns structured notes, grows the question bank
/// and drafts a thank-you email (sending always asks for confirmation).
class DebriefScreen extends StatefulWidget {
  const DebriefScreen({super.key, this.interview});
  final Map<String, dynamic>? interview;
  @override
  State<DebriefScreen> createState() => _DebriefScreenState();
}

class _DebriefScreenState extends State<DebriefScreen> {
  final _text = TextEditingController();
  final _company = TextEditingController();
  final _role = TextEditingController();
  final _to = TextEditingController();
  final _subject = TextEditingController();
  final _body = TextEditingController();
  final _stt = SpeechToText();
  final _bank = Resource<Map<String, dynamic>>(() async => asMap(await Session.I.api.get('/question-bank')));
  final _past = Resource<List<Map<String, dynamic>>>(() async => asList(await Session.I.api.get('/debriefs')));
  Map<String, dynamic>? _res;
  bool _sttReady = false;
  bool _listening = false;
  bool _busy = false;
  String _base = '';

  @override
  void initState() {
    super.initState();
    _bank.load();
    _past.load();
  }

  @override
  void dispose() {
    _stt.cancel();
    for (final c in [_text, _company, _role, _to, _subject, _body]) {
      c.dispose();
    }
    _bank.dispose();
    _past.dispose();
    super.dispose();
  }

  Future<void> _mic() async {
    if (_listening) {
      await _stt.stop();
      if (mounted) setState(() => _listening = false);
      return;
    }
    if (!_sttReady) {
      try {
        _sttReady = await _stt.initialize(onStatus: (s) {
          if ((s == 'done' || s == 'notListening') && mounted) setState(() => _listening = false);
        }, onError: (_) {
          if (mounted) setState(() => _listening = false);
        });
      } catch (_) {
        _sttReady = false;
      }
    }
    if (!_sttReady) {
      if (mounted) toast(context, 'Speech recognition is not available. Type your notes instead.', error: true);
      return;
    }
    _base = _text.text.isEmpty ? '' : '${_text.text.trim()} ';
    setState(() => _listening = true);
    await _stt.listen(
      listenOptions: SpeechListenOptions(partialResults: true, cancelOnError: true, listenMode: ListenMode.dictation, pauseFor: const Duration(seconds: 6)),
      onResult: (r) {
        if (mounted) _text.text = _base + r.recognizedWords;
      },
    );
  }

  void _show(Map<String, dynamic> d) {
    final t = asMap(d['thank_you']);
    _to.text = '${t['to'] ?? ''}';
    _subject.text = '${t['subject'] ?? ''}';
    _body.text = '${t['body'] ?? ''}';
    setState(() => _res = d);
  }

  Future<void> _save() async {
    final iv = widget.interview;
    setState(() => _busy = true);
    try {
      final d = asMap(await Session.I.api.post('/debriefs', data: {
        'text': _text.text,
        if (iv != null) 'interview_id': iv['id'] else ...{'company': _company.text.trim(), 'role': _role.text.trim()},
      }));
      _text.clear();
      _show(d);
      await Future.wait([_bank.load(), _past.load()]);
    } on ApiException catch (e) {
      if (mounted) toast(context, e.message, error: true);
    }
    if (mounted) setState(() => _busy = false);
  }

  Future<void> _send() async {
    final id = '${_res!['id']}';
    final ok = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        title: const Text('Send thank-you?'),
        content: Text('This sends the email from your Gmail to ${_to.text.trim()}.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('Cancel')),
          TextButton(onPressed: () => Navigator.pop(c, true), child: const Text('Send')),
        ],
      ),
    );
    if (ok != true) return;
    setState(() => _busy = true);
    try {
      final d = asMap(await Session.I.api.post('/debriefs/$id/thank-you/send', data: {'to': _to.text.trim(), 'approved': true, 'subject': _subject.text, 'body': _body.text}));
      _show(d);
      if (mounted) toast(context, 'Thank-you sent');
    } on ApiException catch (e) {
      if (mounted) toast(context, e.message, error: true);
    }
    if (mounted) setState(() => _busy = false);
  }

  Future<void> _delete(String id) async {
    try {
      await Session.I.api.request('DELETE', '/debriefs/$id');
      if (_res?['id'] == id) setState(() => _res = null);
      await Future.wait([_bank.load(), _past.load()]);
    } on ApiException catch (e) {
      if (mounted) toast(context, e.message, error: true);
    }
  }

  Widget _list(String title, List items, Color color) => Padding(
        padding: const EdgeInsets.only(bottom: 10),
        child: GlassCard(
          radius: R.md,
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(title, style: TextStyle(color: color, fontWeight: FontWeight.w700)),
            const SizedBox(height: 8),
            if (items.isEmpty) Text('Nothing detected', style: T.small),
            for (final x in items) Padding(padding: const EdgeInsets.only(bottom: 6), child: Text('•  $x')),
          ]),
        ),
      );

  @override
  Widget build(BuildContext context) {
    final iv = widget.interview;
    final r = _res;
    final sent = r != null && asMap(r['thank_you'])['status'] == 'sent';
    return Scaffold(
      backgroundColor: C.bg,
      body: SafeArea(
        child: Stack(children: [
          ListView(padding: const EdgeInsets.fromLTRB(20, 64, 20, 40), children: [
            Text('Debrief', style: T.display),
            const SizedBox(height: 6),
            Text(iv != null ? '${iv['role'] ?? ''} at ${iv['company'] ?? ''}' : 'Say or type what happened in the interview.', style: T.small),
            const SizedBox(height: 14),
            if (iv == null) ...[
              TextField(controller: _company, decoration: const InputDecoration(hintText: 'Company')),
              const SizedBox(height: 8),
              TextField(controller: _role, decoration: const InputDecoration(hintText: 'Role')),
              const SizedBox(height: 8),
            ],
            TextField(controller: _text, minLines: 5, maxLines: 10, decoration: const InputDecoration(hintText: 'They asked me about... It went well when... I struggled with... Next step is...')),
            const SizedBox(height: 10),
            Row(spacing: 10, children: [
              Expanded(child: PrimaryButton(label: _listening ? 'Stop' : 'Speak', icon: _listening ? Icons.stop_rounded : Icons.mic_rounded, ghost: true, onTap: _mic)),
              Expanded(child: PrimaryButton(label: 'Create notes', icon: Icons.auto_awesome_rounded, busy: _busy, onTap: _busy ? null : _save)),
            ]),
            if (r != null) ...[
              const SectionTitle('Your notes'),
              _list('Questions they asked', asList(r['questions']), C.warn),
              _list('What went well', asList(r['went_well']), C.good),
              _list('To improve', asList(r['to_improve']), C.bad),
              _list('Next steps', [...asList(r['next_steps']), ...asList(r['dates']).map((d) => 'Date mentioned: $d')], C.violet),
              if (asList(r['skills']).isNotEmpty) Wrap(spacing: 6, runSpacing: 6, children: [for (final s in asList(r['skills'])) Pill('$s', color: C.primary)]),
              const SectionTitle('Thank-you email draft'),
              GlassCard(
                radius: R.md,
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  TextField(controller: _to, enabled: !sent, keyboardType: TextInputType.emailAddress, decoration: const InputDecoration(hintText: 'Recipient email')),
                  const SizedBox(height: 8),
                  TextField(controller: _subject, enabled: !sent),
                  const SizedBox(height: 8),
                  TextField(controller: _body, enabled: !sent, minLines: 6, maxLines: 12),
                  const SizedBox(height: 8),
                  Text('Built only from your notes, the company, the role and your name. Nothing is sent without your approval.', style: T.small),
                  const SizedBox(height: 10),
                  Row(spacing: 10, children: [
                    Expanded(child: PrimaryButton(label: 'Copy', icon: Icons.copy_rounded, ghost: true, onTap: () => copyText(context, '${_subject.text}\n\n${_body.text}'))),
                    if (!sent) Expanded(child: PrimaryButton(label: 'Send', icon: Icons.send_rounded, busy: _busy, onTap: _busy ? null : () => _to.text.contains('@') ? _send() : toast(context, 'Enter the recipient email', error: true))),
                  ]),
                ]),
              ),
            ],
            const SectionTitle('Question bank'),
            ListenableBuilder(
              listenable: _bank,
              builder: (context, _) {
                final items = asList(_bank.data?['items']);
                if (items.isEmpty) return GlassCard(child: Text('No questions yet.', style: T.small));
                return Column(children: [
                  for (final q in items)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: GlassCard(
                        radius: R.md,
                        padding: const EdgeInsets.all(14),
                        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          Text('${asMap(q)['text']}', style: const TextStyle(fontWeight: FontWeight.w600)),
                          const SizedBox(height: 6),
                          Wrap(spacing: 6, runSpacing: 6, children: [
                            for (final c in asList(asMap(q)['companies'])) Pill('$c', color: C.muted),
                            for (final s in asList(asMap(q)['skills'])) Pill('$s', color: C.good),
                          ]),
                        ]),
                      ),
                    ),
                ]);
              },
            ),
            const SectionTitle('Past debriefs'),
            ListenableBuilder(
              listenable: _past,
              builder: (context, _) {
                final items = _past.data ?? const [];
                if (items.isEmpty) return GlassCard(child: Text('None', style: T.small));
                return Column(children: [
                  for (final d in items)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: GlassCard(
                        radius: R.md,
                        padding: const EdgeInsets.all(14),
                        onTap: () => _show(d),
                        child: Row(children: [
                          Expanded(child: Text('${d['role']}  ·  ${d['company']}\n${d['date'] ?? ''}  ·  ${asList(d['questions']).length} questions')),
                          IconButton(icon: const Icon(Icons.delete_outline_rounded), onPressed: () => _delete('${d['id']}')),
                        ]),
                      ),
                    ),
                ]);
              },
            ),
          ]),
          Positioned(left: 12, top: 8, child: IconButton.filledTonal(onPressed: () => Navigator.of(context).maybePop(), icon: const Icon(Icons.arrow_back_rounded))),
        ]),
      ),
    );
  }
}
