import 'package:image_picker/image_picker.dart';
import 'package:material_ui/material_ui.dart';

import '../../core/api.dart';
import '../../core/motion.dart';
import '../../core/resource.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/dot_ring.dart';
import '../../core/widgets/forms.dart';
import '../../core/widgets/kit.dart';
import '../../core/widgets/ui.dart';
import '../mock/mock_setup_screen.dart';
import 'email_draft.dart';
import 'job_context.dart';

/// Opens "Ask Saige about this job" for a job (or a screenshot that is read on the phone first).
Future<void> openJobChat(BuildContext context, {JobContext? job, String? imagePath, bool replace = false}) {
  final route = DepthRoute<void>(builder: (_) => JobChatScreen(job: job, imagePath: imagePath));
  return replace ? Navigator.of(context).pushReplacement(route) : Navigator.of(context).push(route);
}

enum _K { text, match, resume, email, questions, contacts, list }

class _Msg {
  _Msg.text(this.me, this.text)
      : kind = _K.text,
        data = null;
  _Msg.card(this.kind, this.data, {this.text = ''}) : me = false;
  final bool me;
  final _K kind;
  final String text;
  final dynamic data;
}

const _chips = <(String, IconData)>[
  ('Check my match', Icons.insights_rounded),
  ('Write ATS resume', Icons.description_rounded),
  ('Draft email to HR', Icons.mail_rounded),
  ('Find HR contacts', Icons.person_search_rounded),
  ('Interview questions', Icons.quiz_rounded),
  ('What\'s missing?', Icons.rule_rounded),
];

/// A Gemini-style chat about one job. Free text goes to the Saige assistant with the job as context; the chips call the
/// same endpoints as the web app (ATS Studio, recruiters, outreach). Nothing is invented: the backend truth guard decides,
/// and nothing is sent until the user reviews it and confirms Send.
class JobChatScreen extends StatefulWidget {
  const JobChatScreen({super.key, this.job, this.imagePath});
  final JobContext? job;
  final String? imagePath;

  @override
  State<JobChatScreen> createState() => _JobChatScreenState();
}

class _JobChatScreenState extends State<JobChatScreen> {
  late JobContext _job = widget.job ?? JobContext();
  final _msgs = <_Msg>[];
  final _input = TextEditingController();
  final _scroll = ScrollController();
  Map<String, dynamic>? _analysis;
  bool _working = false;
  String _status = '';

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _boot());
  }

  @override
  void dispose() {
    _input.dispose();
    _scroll.dispose();
    super.dispose();
  }

  // ---------------------------------------------------------------- plumbing

  void _add(_Msg m) {
    if (!mounted) return;
    setState(() => _msgs.add(m));
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) _scroll.animateTo(_scroll.position.maxScrollExtent + 300, duration: const Duration(milliseconds: 350), curve: Curves.easeOutCubic);
    });
  }

  void _say(String t) => _add(_Msg.text(false, t));

  /// Runs one step with a busy indicator; failures become a friendly assistant message.
  Future<void> _step(String status, Future<void> Function() body) async {
    if (_working) return;
    setState(() {
      _working = true;
      _status = status;
    });
    try {
      await body();
    } on ApiException catch (e) {
      _say(e.offline ? 'You are offline. Connect and try again.' : friendly(e));
    } catch (_) {
      _say('Something went wrong. Try again.');
    }
    if (mounted) setState(() => _working = false);
  }

  Future<void> _boot() async {
    if (widget.imagePath != null) {
      await _step('Reading the screenshot on your phone...', () async {
        final text = await readImageText(widget.imagePath!);
        if (text == null) {
          _say('I could not read any text in that picture. Try a sharper screenshot, or paste the job description below.');
          return;
        }
        _job = jobContextFromText(text);
        await _enrich();
        _say(_readSummary());
        await _analyze(greet: true);
      });
    } else if (_job.hasJd) {
      await _step('Reading the job...', () async {
        await _enrich();
        await _analyze(greet: true);
      });
    } else {
      _say('Hi ${Session.I.firstName}. Paste the job description (or attach a screenshot with the picture button) and I will check it against your verified profile.');
    }
  }

  String _readSummary() {
    final bits = <String>[
      if (_job.title.isNotEmpty) 'role: ${_job.title}',
      if (_job.company.isNotEmpty) 'company: ${_job.company}',
      if (_job.location != null) 'location: ${_job.location}',
      if (_job.emails.isNotEmpty) 'email: ${_job.emails.take(2).join(', ')}',
    ];
    return bits.isEmpty ? 'I read the screenshot but could not find the role or company. Tell me if I got something wrong.' : 'I read the screenshot. Found ${bits.join(' · ')}.';
  }

  /// Fills a missing role or company with the server's detector (same one ATS Studio uses).
  Future<void> _enrich() async {
    if (_job.text.trim().length < 30 || (_job.title.isNotEmpty && _job.company.isNotEmpty)) return;
    try {
      final d = asMap(await Session.I.api.post('/studio/detect', data: {'jd_text': _job.text}));
      if (_job.title.isEmpty && '${d['title'] ?? ''}'.isNotEmpty) _job.title = '${d['title']}';
      if (_job.company.isEmpty && '${d['company'] ?? ''}'.isNotEmpty) _job.company = '${d['company']}';
      if (mounted) setState(() {});
    } catch (_) {}
  }

  Future<Map<String, dynamic>> _ensureAnalysis() async {
    final cached = _analysis;
    if (cached != null) return cached;
    final a = asMap(await Session.I.api.post('/studio/analyze', data: _job.jdBody()));
    _analysis = a;
    if (_job.title.isEmpty && '${a['title'] ?? ''}'.isNotEmpty) _job.title = '${a['title']}';
    if (_job.company.isEmpty && '${a['company'] ?? ''}'.isNotEmpty) _job.company = '${a['company']}';
    _job.score = a['score'] as num? ?? _job.score;
    if (mounted) setState(() {});
    return a;
  }

  Future<void> _analyze({bool greet = false}) async {
    final a = await _ensureAnalysis();
    final score = (a['score'] as num?)?.round();
    final role = _job.title.isEmpty ? 'this job' : _job.title;
    final at = _job.company.isEmpty ? '' : ' at ${_job.company}';
    _add(_Msg.card(_K.match, a, text: greet ? 'Hi ${Session.I.firstName}. I read $role$at. ${score == null ? '' : 'Your match is $score%. '}What would you like to do?' : ''));
  }

  // ---------------------------------------------------------------- chip actions

  Future<void> _chip(String label) async {
    if (_working) return;
    tick();
    if (!_job.hasJd) {
      _add(_Msg.text(true, label));
      _say('I need the job description first. Paste it below or attach a screenshot.');
      return;
    }
    _add(_Msg.text(true, label));
    switch (label) {
      case 'Check my match':
        await _step('Matching against your verified profile...', _analyze);
      case 'Write ATS resume':
        await _step('Writing your ATS resume from verified facts...', _resume);
      case 'Draft email to HR':
        await _step('Drafting the email...', () => _email());
      case 'Find HR contacts':
        await _step('Looking for contacts...', _contacts);
      case 'Interview questions':
        await _step('Preparing questions...', _interview);
      default:
        await _step('Comparing with your profile...', _missing);
    }
  }

  Future<void> _resume() async {
    final r = asMap(await Session.I.api.post('/studio/resume', data: {..._job.jdBody(), 'template': 'modern'}));
    success();
    _add(_Msg.card(_K.resume, r));
  }

  Future<void> _email({Map<String, String> answers = const {}, String? to}) async {
    final emails = _job.emails;
    final r = asMap(await Session.I.api.post('/studio/apply/draft', data: {
      ..._job.jdBody(),
      'template': 'modern',
      if ((to ?? (emails.isEmpty ? null : emails.first)) != null) 'to': to ?? emails.first,
      if (answers.isNotEmpty) 'answers': answers,
    }));
    if (r['status'] == 'needs_details') {
      _add(_Msg.card(_K.questions, asList(r['questions']), text: 'Before I write it, I need a few facts for this post. They are saved to your profile, so I only ask once.'));
      return;
    }
    final d = EmailDraft.fromApply(r, company: _job.company);
    if (d.to.isEmpty) {
      _say('I did not find an email address in the job text, so add the recipient below. I built a resume for it too.');
    } else {
      _say('Here is the email to ${d.to}. Edit anything, then tap Send.');
    }
    _add(_Msg.card(_K.email, d));
  }

  Future<void> _contacts() async {
    final company = _job.company.trim();
    final people = <Map<String, dynamic>>[];
    if (company.isNotEmpty) {
      try {
        people.addAll(asList(await Session.I.api.get('/recruiters', query: {'company': company})));
      } catch (_) {}
    }
    _add(_Msg.card(_K.contacts, {'company': company, 'people': people, 'emails': _job.emails}));
  }

  Future<void> _interview() async {
    final a = await _ensureAnalysis();
    final qs = <String>[];
    final skills = asMap(a['skills']);
    for (final s in asList(skills['required'])) {
      final name = '${s['name']}';
      qs.add(s['have'] == true ? 'Tell me about a project where you used $name. What was your part?' : 'This role asks for $name. How would you get productive with it quickly?');
    }
    for (final r in (a['responsibilities'] as List? ?? const []).take(3)) {
      qs.add('How would you approach this responsibility: $r');
    }
    qs.addAll(['Why do you want this role${_job.company.isEmpty ? '' : ' at ${_job.company}'}?', 'Walk me through your most relevant experience for this job.']);
    _add(_Msg.card(_K.list, {
      'title': 'Questions to practise',
      'items': qs.take(10).toList(),
      'note': 'Answer from your own experience only. Practise out loud in a mock interview.',
      'action': 'Practise now',
    }));
  }

  Future<void> _missing() async {
    final a = await _ensureAnalysis();
    final items = <String>[];
    for (final s in asList(asMap(a['skills'])['required'])) {
      if (s['have'] != true) items.add('${s['name']} (required)');
    }
    for (final s in asList(asMap(a['skills'])['preferred'])) {
      if (s['have'] != true) items.add('${s['name']} (nice to have)');
    }
    for (final g in (a['gaps'] as List? ?? const [])) {
      items.add(g is Map ? '${g['text'] ?? g['label'] ?? ''}' : '$g');
    }
    final seen = <String>{};
    final uniq = [for (final i in items) if (i.trim().isNotEmpty && seen.add(i)) i];
    if (uniq.isEmpty) {
      _say('I found nothing important missing: your verified profile covers what this job asks for.');
      return;
    }
    _add(_Msg.card(_K.list, {
      'title': 'What is missing for this job',
      'items': uniq.take(10).toList(),
      'note': 'Saige only adds skills you can back up. If you really have one, add it in Profile and the match updates.',
    }));
  }

  Future<void> _draftOutreach(Map<String, dynamic> c) async {
    final role = '${c['role']}';
    final kind = role == 'hiring_manager' ? 'hiring_manager' : (role == 'referral' || role == 'alumni') ? 'referral' : 'cold';
    await _step('Drafting a message to ${c['name']}...', () async {
      final o = asMap(await Session.I.api.post('/outreach/draft', data: {'contact_id': c['id'], 'kind': kind, if (_job.jobId != null) 'job_id': _job.jobId}));
      final d = EmailDraft.fromOutreach(o, to: '${c['email'] ?? ''}');
      _say('Drafted a message to ${c['name']}. Every line is checked against your verified profile.');
      _add(_Msg.card(_K.email, d));
    });
  }

  // ---------------------------------------------------------------- free text, images

  Future<void> _submit(String raw) async {
    final t = raw.trim();
    if (t.isEmpty || _working) return;
    _input.clear();
    _add(_Msg.text(true, t));
    if (!_job.hasJd) {
      if (t.length >= 40) {
        await _step('Reading the job...', () async {
          _job = jobContextFromText(t);
          _analysis = null;
          await _enrich();
          await _analyze(greet: true);
        });
      } else {
        _say('That is a bit short for a job description. Paste the whole post or attach a screenshot.');
      }
      return;
    }
    await _step('Thinking...', () async {
      final turns = _msgs.where((m) => m.kind == _K.text && m.text.isNotEmpty).toList();
      final recent = turns.skip(turns.length > 10 ? turns.length - 10 : 0);
      final r = asMap(await Session.I.api.post('/assistant/chat', data: {
        'messages': [
          {'role': 'user', 'content': _job.assistantPreamble()},
          {'role': 'assistant', 'content': 'Got it. Ask me anything about this job.'},
          for (final m in recent) {'role': m.me ? 'user' : 'assistant', 'content': m.text.length > 3900 ? m.text.substring(0, 3900) : m.text},
        ],
        'language': 'en',
      }));
      _say('${r['reply'] ?? 'I do not have an answer for that.'}');
    });
  }

  Future<void> _attach() async {
    if (_working) return;
    XFile? f;
    try {
      f = await ImagePicker().pickImage(source: ImageSource.gallery, maxWidth: 2400);
    } catch (_) {
      if (mounted) toast(context, 'Could not open the photo.', error: true);
    }
    if (f == null) return;
    final path = f.path;
    _add(_Msg.text(true, 'Screenshot attached'));
    await _step('Reading the screenshot on your phone...', () async {
      final text = await readImageText(path);
      if (text == null) {
        _say('I could not read any text in that picture. Try a sharper one.');
        return;
      }
      if (_job.hasJd && _job.jobId == null && _job.careerJobId == null) {
        _job.text = '${_job.text.trim()}\n$text';
        _job.emails = extractEmails(_job.text);
      } else {
        _job = jobContextFromText(text);
      }
      _analysis = null;
      await _enrich();
      _say(_readSummary());
      await _analyze(greet: true);
    });
  }

  // ---------------------------------------------------------------- UI

  @override
  Widget build(BuildContext context) => Scaffold(
        backgroundColor: C.bg,
        body: SafeArea(
          child: Column(children: [
            _header(),
            Expanded(
              child: SingleChildScrollView(
                controller: _scroll,
                physics: const BouncingScrollPhysics(),
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  for (final m in _msgs) _row(m),
                  if (_working)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 8),
                      child: Row(children: [const DotRing(size: 30, dots: 12), const SizedBox(width: 12), Expanded(child: Text(_status, style: T.small))]),
                    ),
                ]),
              ),
            ),
            SizedBox(
              height: 46,
              child: ListView.separated(
                scrollDirection: Axis.horizontal,
                physics: const BouncingScrollPhysics(),
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 3),
                itemCount: _chips.length,
                separatorBuilder: (_, _) => const SizedBox(width: 8),
                itemBuilder: (_, i) {
                  final (label, icon) = _chips[i];
                  return Pressable(
                    onTap: _working ? null : () => _chip(label),
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 14),
                      decoration: BoxDecoration(color: C.surface2, borderRadius: BorderRadius.circular(99), border: Border.all(color: C.line)),
                      child: Row(children: [
                        Icon(icon, size: 16, color: _working ? C.muted : C.primary),
                        const SizedBox(width: 7),
                        Text(label, style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13.5, color: _working ? C.muted : C.text)),
                      ]),
                    ),
                  );
                },
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 6, 16, 12),
              child: Row(children: [
                Pressable(
                  onTap: _working ? null : _attach,
                  child: Container(width: 50, height: 50, decoration: BoxDecoration(shape: BoxShape.circle, color: C.surface2, border: Border.all(color: C.line)), child: Icon(Icons.image_rounded, color: C.text, size: 22)),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: TextField(
                    controller: _input,
                    minLines: 1,
                    maxLines: 4,
                    textInputAction: TextInputAction.send,
                    onSubmitted: _submit,
                    decoration: InputDecoration(hintText: _job.hasJd ? 'Ask about this job' : 'Paste the job description'),
                  ),
                ),
                const SizedBox(width: 8),
                Pressable(
                  onTap: () => _submit(_input.text),
                  child: Container(width: 50, height: 50, decoration: BoxDecoration(color: C.primary, shape: BoxShape.circle), child: Icon(Icons.arrow_upward_rounded, color: C.onPrimary)),
                ),
              ]),
            ),
          ]),
        ),
      );

  Widget _header() => Padding(
        padding: const EdgeInsets.fromLTRB(12, 8, 16, 4),
        child: Row(children: [
          Pressable(
            onTap: () => Navigator.of(context).maybePop(),
            child: Container(width: 46, height: 46, decoration: BoxDecoration(shape: BoxShape.circle, color: C.surface2, border: Border.all(color: C.line)), child: const Icon(Icons.arrow_back_rounded)),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Container(
              height: 46,
              padding: const EdgeInsets.symmetric(horizontal: 16),
              decoration: BoxDecoration(color: C.surface2, borderRadius: BorderRadius.circular(99), border: Border.all(color: C.line)),
              child: Row(children: [
                Icon(Icons.work_rounded, size: 17, color: C.primary),
                const SizedBox(width: 8),
                Expanded(child: Text(_job.label, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14.5))),
                if (_job.score != null) Text('${_job.score!.round()}%', style: TextStyle(fontWeight: FontWeight.w800, color: scoreColor(_job.score!.toDouble()))),
              ]),
            ),
          ),
        ]),
      );

  Widget _bubble(String text, {required bool me}) => Align(
        alignment: me ? Alignment.centerRight : Alignment.centerLeft,
        child: Container(
          margin: const EdgeInsets.symmetric(vertical: 5),
          constraints: BoxConstraints(maxWidth: MediaQuery.sizeOf(context).width * 0.84),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          decoration: BoxDecoration(
            color: me ? C.primary : C.surface2,
            borderRadius: BorderRadius.only(topLeft: const Radius.circular(22), topRight: const Radius.circular(22), bottomLeft: Radius.circular(me ? 22 : 6), bottomRight: Radius.circular(me ? 6 : 22)),
            border: me ? null : Border.all(color: C.line),
          ),
          child: SelectableText(text, style: T.body.copyWith(color: me ? C.onPrimary : C.text)),
        ),
      );

  Widget _card(Widget child) => Container(
        width: double.infinity,
        margin: const EdgeInsets.symmetric(vertical: 5),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(color: C.surface, borderRadius: BorderRadius.circular(R.md), border: Border.all(color: C.line)),
        child: child,
      );

  Widget _row(_Msg m) {
    final w = switch (m.kind) {
      _K.text => _bubble(m.text, me: m.me),
      _K.match => _matchCard(m),
      _K.resume => _resumeCard(asMap(m.data)),
      _K.email => _card(EmailDraftCard(draft: m.data as EmailDraft, compact: true)),
      _K.questions => _card(_QuestionsCard(intro: m.text, questions: (m.data as List).cast<Map<String, dynamic>>(), onSubmit: (a) {
          _add(_Msg.text(true, 'Answered ${a.length} question${a.length == 1 ? '' : 's'}'));
          _step('Drafting the email...', () => _email(answers: a));
        })),
      _K.contacts => _contactsCard(asMap(m.data)),
      _K.list => _listCard(asMap(m.data)),
    };
    return Stagger(index: 0, dx: m.me ? 30 : -30, child: w);
  }

  Widget _matchCard(_Msg m) {
    final a = asMap(m.data);
    final score = (a['score'] as num?) ?? 0;
    final skills = asMap(a['skills']);
    final all = [...asList(skills['required']), ...asList(skills['preferred'])];
    final have = [for (final s in all) if (s['have'] == true) '${s['name']}'];
    final miss = [for (final s in all) if (s['have'] != true) '${s['name']}'];
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      if (m.text.isNotEmpty) _bubble(m.text, me: false),
      _card(Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          ScoreRing(score: score, size: 96, dots: 30),
          const SizedBox(width: 16),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('${asMap(a['verdict'])['label'] ?? 'Match'}', style: T.h2),
              if ('${a['summary'] ?? ''}'.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 4), child: Text('${a['summary']}', style: T.small, maxLines: 4, overflow: TextOverflow.ellipsis)),
            ]),
          ),
        ]),
        if (have.isNotEmpty) ...[
          const SizedBox(height: 14),
          Text('YOU HAVE', style: T.label),
          const SizedBox(height: 8),
          Wrap(spacing: 6, runSpacing: 6, children: [for (final s in have.take(14)) Pill(s, color: C.good, filled: true)]),
        ],
        if (miss.isNotEmpty) ...[
          const SizedBox(height: 14),
          Text('MISSING', style: T.label),
          const SizedBox(height: 8),
          Wrap(spacing: 6, runSpacing: 6, children: [for (final s in miss.take(12)) Pill(s, color: C.warn, filled: true)]),
        ],
      ])),
    ]);
  }

  Widget _resumeCard(Map<String, dynamic> r) {
    final id = '${r['id']}';
    final ats = asMap(r['ats'])['score'];
    final changes = r['changes'] is List ? (r['changes'] as List).length : null;
    Widget file(String label, String fmt) => Expanded(
          child: PrimaryButton(
            label: label,
            icon: Icons.download_rounded,
            ghost: fmt != 'pdf',
            onTap: () => downloadAndShare(context, '/studio/resumes/$id/download', query: {'format': fmt}, fallbackName: 'resume.$fmt'),
          ),
        );
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      _bubble('Your ATS resume for ${_job.title.isEmpty ? 'this job' : _job.title} is ready. Every line comes from your verified profile.', me: false),
      _card(Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Container(width: 46, height: 46, decoration: BoxDecoration(shape: BoxShape.circle, color: C.primarySoft), child: Icon(Icons.description_rounded, color: C.primary)),
          const SizedBox(width: 12),
          Expanded(child: Text('${r['name'] ?? r['title'] ?? 'ATS resume'}', maxLines: 2, overflow: TextOverflow.ellipsis, style: T.h2.copyWith(fontSize: 16))),
          if (ats is num) Pill('ATS ${ats.round()}', color: scoreColor(ats.toDouble()), filled: true),
        ]),
        if (changes != null) Padding(padding: const EdgeInsets.only(top: 8), child: Text('$changes truthful changes for this job.', style: T.small)),
        const SizedBox(height: 14),
        Row(children: [file('PDF', 'pdf'), const SizedBox(width: 10), file('DOCX', 'docx')]),
      ])),
    ]);
  }

  Widget _contactsCard(Map<String, dynamic> d) {
    final company = '${d['company']}';
    final people = asList(d['people']);
    final emails = (d['emails'] as List).cast<String>();
    const roles = ['HR', 'Talent Acquisition', 'Technical Recruiter', 'Hiring Manager'];
    return _card(Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(company.isEmpty ? 'HR contacts' : 'HR contacts at $company', style: T.h2),
      const SizedBox(height: 10),
      if (emails.isNotEmpty) ...[
        Text('IN THE POST', style: T.label),
        const SizedBox(height: 8),
        for (final e in emails.take(3))
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Row(children: [
              Expanded(child: Text(e, style: T.body.copyWith(fontWeight: FontWeight.w600))),
              Pressable(onTap: _working ? null : () => _step('Drafting the email...', () => _email(to: e)), child: const Pill('Draft email', filled: true)),
            ]),
          ),
        const SizedBox(height: 6),
      ],
      if (people.isNotEmpty) ...[
        Text('YOUR CONTACTS', style: T.label),
        const SizedBox(height: 8),
        for (final p in people.take(6))
          Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: Row(children: [
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text('${p['name']}', style: const TextStyle(fontWeight: FontWeight.w700)),
                  Text([p['title'], p['email']].where((x) => x != null && '$x'.isNotEmpty).join(' · '), maxLines: 1, overflow: TextOverflow.ellipsis, style: T.small),
                ]),
              ),
              if ('${p['email'] ?? ''}'.isNotEmpty && p['unsubscribed'] != true) Pressable(onTap: _working ? null : () => _draftOutreach(p), child: const Pill('Draft email', filled: true)),
            ]),
          ),
      ] else if (emails.isEmpty)
        Text('You have no saved contacts here yet. Open a search below, pick the right person on LinkedIn yourself, then add them in Recruiters.', style: T.small),
      const SizedBox(height: 10),
      Text('FIND THEM ON LINKEDIN', style: T.label),
      const SizedBox(height: 8),
      Wrap(spacing: 6, runSpacing: 6, children: [
        for (final r in roles)
          Pressable(
            onTap: () => openUrl(context, 'https://www.linkedin.com/search/results/people/?keywords=${Uri.encodeQueryComponent('$r $company')}'),
            child: Pill(r, color: C.text),
          ),
      ]),
      const SizedBox(height: 8),
      Text('You open these yourself. Saige never scrapes LinkedIn.', style: T.small),
    ]));
  }

  Widget _listCard(Map<String, dynamic> d) {
    final items = (d['items'] as List).map((e) => '$e').toList();
    return _card(Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text('${d['title']}', style: T.h2),
      const SizedBox(height: 10),
      for (final i in items) Dot(i, C.primary),
      if ('${d['note'] ?? ''}'.isNotEmpty) Text('${d['note']}', style: T.small),
      if (d['action'] != null) ...[
        const SizedBox(height: 12),
        PrimaryButton(
          label: '${d['action']}',
          icon: Icons.record_voice_over_rounded,
          ghost: true,
          onTap: () => pushDepth(context, (_) => MockSetupScreen(initialRole: _job.title.isEmpty ? null : (_job.company.isEmpty ? _job.title : '${_job.title} at ${_job.company}'))),
        ),
      ],
    ]));
  }
}

class _QuestionsCard extends StatefulWidget {
  const _QuestionsCard({required this.intro, required this.questions, required this.onSubmit});
  final String intro;
  final List<Map<String, dynamic>> questions;
  final void Function(Map<String, String>) onSubmit;
  @override
  State<_QuestionsCard> createState() => _QuestionsCardState();
}

class _QuestionsCardState extends State<_QuestionsCard> {
  late final _c = {for (final q in widget.questions) '${q['key']}': TextEditingController()};
  bool _done = false;

  @override
  void dispose() {
    for (final c in _c.values) {
      c.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(widget.intro, style: T.body),
        const SizedBox(height: 12),
        for (final q in widget.questions) ...[
          LabeledField(label: '${q['label']}', controller: _c['${q['key']}']!, keyboard: q['type'] == 'number' ? TextInputType.number : null),
          const SizedBox(height: 10),
        ],
        PrimaryButton(
          label: _done ? 'Sent' : 'Continue',
          onTap: _done
              ? null
              : () {
                  final a = {for (final e in _c.entries) if (e.value.text.trim().isNotEmpty) e.key: e.value.text.trim()};
                  if (a.isEmpty) return toast(context, 'Fill in at least one answer.', error: true);
                  setState(() => _done = true);
                  widget.onSubmit(a);
                },
        ),
      ]);
}
