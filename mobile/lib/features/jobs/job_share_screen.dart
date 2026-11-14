import 'package:google_mlkit_text_recognition/google_mlkit_text_recognition.dart';
import 'package:image_picker/image_picker.dart';
import 'package:material_ui/material_ui.dart';

import '../../core/api.dart';
import '../../core/motion.dart';
import '../../core/resource.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/kit.dart';
import '../../core/widgets/ui.dart';
import '../mock/mock_setup_screen.dart';

/// A job that arrived from outside the app: shared text or link (LinkedIn, Naukri, Chrome...),
/// a shared screenshot, or a photo of a printed job description.
///
/// Only Greenhouse, Lever and Ashby links are fetched (their public APIs). For any other link we use the text
/// the user shared and ask them to paste the description: Saige never loads LinkedIn or Naukri pages.
class JobShareScreen extends StatefulWidget {
  const JobShareScreen({super.key, this.sharedText, this.imagePath, this.scan = false});
  final String? sharedText;
  final String? imagePath;
  final bool scan; // open the camera straight away

  @override
  State<JobShareScreen> createState() => _JobShareScreenState();
}

final _urlRe = RegExp(r'https?://[^\s<>"]+');

/// True for job links whose boards have an official public API (see backend studio/joblink.py).
bool isSupportedJobLink(String url) {
  final h = Uri.tryParse(url)?.host.toLowerCase() ?? '';
  return h.endsWith('greenhouse.io') || h == 'jobs.lever.co' || h.endsWith('.lever.co') || h == 'jobs.ashbyhq.com' || h.endsWith('ashbyhq.com');
}

class _JobShareScreenState extends State<JobShareScreen> {
  final _jd = TextEditingController();
  final _title = TextEditingController();
  final _company = TextEditingController();
  String? _link;
  String? _deadline;
  String? _note;
  bool _busy = false;
  bool _ocr = false;
  bool _building = false;
  bool _saved = false;
  Map<String, dynamic>? _analysis;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _start());
  }

  @override
  void dispose() {
    _jd.dispose();
    _title.dispose();
    _company.dispose();
    super.dispose();
  }

  Future<void> _start() async {
    if (widget.scan) return _scan();
    if (widget.imagePath != null) return _recognise(widget.imagePath!);
    final shared = widget.sharedText ?? '';
    final urls = _urlRe.allMatches(shared).map((m) => m.group(0)!).toList();
    final rest = shared.replaceAll(_urlRe, '').trim();
    _link = urls.isEmpty ? null : urls.first;
    if (_link != null && isSupportedJobLink(_link!)) {
      setState(() => _busy = true);
      try {
        final r = asMap(await Session.I.api.post('/studio/fetch-jd', data: {'url': _link}));
        _jd.text = '${r['jd_text'] ?? ''}';
        if ('${r['title'] ?? ''}'.isNotEmpty) _title.text = '${r['title']}';
        if ('${r['company'] ?? ''}'.isNotEmpty) _company.text = '${r['company']}';
      } on ApiException catch (e) {
        _note = e.message;
        _jd.text = rest;
      }
      if (mounted) setState(() => _busy = false);
    } else {
      _jd.text = rest;
      if (_link != null) {
        _note = 'Saige does not open job pages for you. Open the job, copy its description and paste it below. '
            '${rest.length >= 30 ? 'The text that came with the link is shown, but it is probably only a title.' : ''}';
      }
    }
    if (_jd.text.trim().length >= 30) await _analyze();
  }

  Future<void> _scan() async {
    try {
      final f = await ImagePicker().pickImage(source: ImageSource.camera, imageQuality: 90, maxWidth: 2400);
      if (f == null) return;
      await _recognise(f.path);
    } catch (_) {
      if (mounted) toast(context, 'Could not open the camera.', error: true);
    }
  }

  Future<void> _gallery() async {
    try {
      final f = await ImagePicker().pickImage(source: ImageSource.gallery, maxWidth: 2400);
      if (f != null) await _recognise(f.path);
    } catch (_) {
      if (mounted) toast(context, 'Could not open the photo.', error: true);
    }
  }

  /// On-device OCR (ML Kit, Latin script). The image never leaves the phone.
  Future<void> _recognise(String path) async {
    setState(() => _ocr = true);
    final rec = TextRecognizer(script: TextRecognitionScript.latin);
    try {
      final r = await rec.processImage(InputImage.fromFilePath(path));
      final text = r.text.trim();
      if (text.isEmpty) {
        _note = 'No text found in the picture. Try again in better light, or type the description.';
      } else {
        _jd.text = _jd.text.trim().isEmpty ? text : '${_jd.text.trim()}\n$text';
        _note = 'Check the recognised text and fix any mistakes before you continue.';
      }
    } catch (_) {
      _note = 'Could not read the picture. You can paste the description instead.';
    } finally {
      await rec.close();
    }
    if (mounted) setState(() => _ocr = false);
    if (_jd.text.trim().length >= 30 && mounted) await _analyze();
  }

  Future<void> _analyze() async {
    final text = _jd.text.trim();
    if (text.length < 30) return toast(context, 'Add the job description first (a few lines).', error: true);
    FocusScope.of(context).unfocus();
    setState(() {
      _busy = true;
      _analysis = null;
      _saved = false;
    });
    final api = Session.I.api;
    try {
      final d = asMap(await api.post('/studio/detect', data: {'jd_text': text}));
      if (_title.text.trim().isEmpty && '${d['title'] ?? ''}'.isNotEmpty) _title.text = '${d['title']}';
      if (_company.text.trim().isEmpty && '${d['company'] ?? ''}'.isNotEmpty) _company.text = '${d['company']}';
      _deadline = d['deadline'] as String?;
      final a = asMap(await api.post('/studio/analyze', data: {'jd_text': text, 'title': _title.text.trim(), 'company': _company.text.trim()}));
      _analysis = a;
      if (_title.text.trim().isEmpty && '${a['title'] ?? ''}'.isNotEmpty) _title.text = '${a['title']}';
    } on ApiException catch (e) {
      if (mounted) toast(context, e.message, error: true);
    }
    if (mounted) setState(() => _busy = false);
  }

  Future<void> _build() async {
    setState(() => _building = true);
    try {
      final r = asMap(await Session.I.api.post('/studio/resume', data: {
        'jd_text': _jd.text.trim(),
        'title': _title.text.trim(),
        'company': _company.text.trim(),
        'template': 'modern',
      }));
      success();
      if (!mounted) return;
      await downloadAndShare(context, '/studio/resumes/${r['id']}/download', query: {'format': 'pdf'}, fallbackName: 'resume.pdf');
    } on ApiException catch (e) {
      if (mounted) toast(context, e.message, error: true);
    }
    if (mounted) setState(() => _building = false);
  }

  Future<void> _save() async {
    if (_title.text.trim().length < 2 || _company.text.trim().isEmpty) {
      return toast(context, 'Fill in the role and the company first.', error: true);
    }
    try {
      final r = asMap(await Session.I.api.post('/jobs/import', data: {
        'title': _title.text.trim(),
        'company': _company.text.trim(),
        'description': _jd.text.trim(),
        if (_link != null) 'application_url': _link,
      }));
      success();
      if (mounted) {
        setState(() => _saved = true);
        toast(context, r['duplicate'] == true ? 'Already saved.' : 'Job saved.');
      }
    } on ApiException catch (e) {
      if (mounted) toast(context, e.message, error: true);
    }
  }

  void _practise() {
    final role = _title.text.trim();
    final co = _company.text.trim();
    pushDepth(context, (_) => MockSetupScreen(initialRole: role.isEmpty ? null : (co.isEmpty ? role : '$role at $co')));
  }

  @override
  Widget build(BuildContext context) {
    final a = _analysis;
    final ready = _jd.text.trim().length >= 30;
    return FeatureScaffold(
      title: widget.scan ? 'Scan a job' : 'Job from share',
      subtitle: 'Match, resume, save or practise',
      child: ListView(
        physics: const BouncingScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(20, 10, 20, 120),
        children: [
          if (_link != null)
            GlassCard(
              padding: const EdgeInsets.all(14),
              child: Row(children: [
                Icon(Icons.link_rounded, color: C.primary),
                const SizedBox(width: 10),
                Expanded(child: Text(_link!, maxLines: 2, overflow: TextOverflow.ellipsis, style: T.small)),
              ]),
            ),
          if (_note != null) ...[
            const SizedBox(height: 10),
            GlassCard(color: C.primarySoft, padding: const EdgeInsets.all(14), child: Text(_note!, style: T.small.copyWith(color: C.text))),
          ],
          const SizedBox(height: 14),
          Row(children: [
            Expanded(child: PrimaryButton(label: 'Scan with camera', icon: Icons.photo_camera_rounded, ghost: true, busy: _ocr, onTap: _scan)),
            const SizedBox(width: 10),
            Expanded(child: PrimaryButton(label: 'From a photo', icon: Icons.image_rounded, ghost: true, busy: _ocr, onTap: _gallery)),
          ]),
          const SizedBox(height: 18),
          LabeledField(label: 'Job description', controller: _jd, lines: 8, hint: 'Paste or scan the description'),
          const SizedBox(height: 12),
          LabeledField(label: 'Role', controller: _title, hint: 'Filled from the description'),
          const SizedBox(height: 12),
          LabeledField(label: 'Company', controller: _company, hint: 'Filled from the description'),
          if (_deadline != null) ...[
            const SizedBox(height: 10),
            Row(children: [Icon(Icons.event_rounded, size: 18, color: C.warn), const SizedBox(width: 8), Text('Apply by $_deadline', style: T.small)]),
          ],
          const SizedBox(height: 16),
          PrimaryButton(label: a == null ? 'Analyse match' : 'Analyse again', icon: Icons.insights_rounded, busy: _busy, onTap: ready ? _analyze : null),
          if (_busy) const LoadingState(),
          if (a != null) ..._analysisView(a),
          if (ready) ...[
            const SizedBox(height: 18),
            PrimaryButton(label: 'Build ATS resume (PDF)', icon: Icons.description_rounded, busy: _building, onTap: _build),
            const SizedBox(height: 10),
            PrimaryButton(label: _saved ? 'Saved' : 'Save job', icon: Icons.bookmark_add_rounded, ghost: true, onTap: _saved ? null : _save),
            const SizedBox(height: 10),
            PrimaryButton(label: 'Practise interview', icon: Icons.record_voice_over_rounded, ghost: true, onTap: _practise),
          ],
        ],
      ),
    );
  }

  List<Widget> _analysisView(Map<String, dynamic> a) {
    final score = (a['score'] as num?)?.toInt() ?? 0;
    final verdict = asMap(a['verdict'])['label'];
    final strengths = asList(a['strengths']);
    final gaps = asList(a['gaps']);
    String line(dynamic x) => x is Map ? '${x['text'] ?? x['label'] ?? x['name'] ?? ''}' : '$x';
    Widget bullets(String head, List items, Color c) => items.isEmpty
        ? const SizedBox.shrink()
        : Padding(
            padding: const EdgeInsets.only(top: 12),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(head.toUpperCase(), style: T.label),
              const SizedBox(height: 6),
              for (final s in items.take(5))
                Padding(
                  padding: const EdgeInsets.only(bottom: 4),
                  child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Padding(padding: const EdgeInsets.only(top: 7, right: 8), child: Icon(Icons.circle, size: 6, color: c)),
                    Expanded(child: Text(line(s), style: T.body)),
                  ]),
                ),
            ]),
          );
    return [
      const SizedBox(height: 14),
      GlassCard(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Text('$score%', style: T.h1.copyWith(color: score >= 70 ? C.good : (score >= 50 ? C.warn : C.bad))),
            const SizedBox(width: 12),
            Expanded(child: Text('${verdict ?? 'Match'}', style: T.h2)),
          ]),
          if ('${a['summary'] ?? ''}'.isNotEmpty) ...[const SizedBox(height: 8), Text('${a['summary']}', style: T.small)],
          bullets('Strengths', strengths, C.good),
          bullets('Gaps', gaps, C.warn),
        ]),
      ),
    ];
  }
}
