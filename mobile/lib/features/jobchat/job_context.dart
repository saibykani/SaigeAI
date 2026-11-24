import 'package:google_mlkit_text_recognition/google_mlkit_text_recognition.dart';

/// One job the user is asking Saige about: pasted/shared text, a recognised screenshot, a saved job or a career-portal job.
class JobContext {
  JobContext({
    this.title = '',
    this.company = '',
    this.text = '',
    this.location,
    this.link,
    this.emails = const [],
    this.jobId,
    this.careerJobId,
    this.score,
  });

  String title;
  String company;
  String text;
  String? location;
  String? link;
  List<String> emails;
  final String? jobId; // saved job (backend /jobs/{id})
  final String? careerJobId; // career-portal job (backend resolves the description)
  num? score; // a match % already known (Radar, job detail)

  bool get hasJd => text.trim().length >= 30 || jobId != null || careerJobId != null;

  /// "QA Engineer · Acme" for the header chip.
  String get label {
    final parts = [title, company].where((e) => e.trim().isNotEmpty).toList();
    return parts.isEmpty ? 'This job' : parts.join(' · ');
  }

  /// The request body shared by /studio/analyze, /studio/resume and /studio/apply/draft.
  Map<String, dynamic> jdBody() => {
        if (careerJobId != null)
          'career_job_id': careerJobId
        else if (jobId != null)
          'job_id': jobId
        else
          'jd_text': text.trim(),
        'title': title.trim(),
        'company': company.trim(),
      };

  /// A short grounding block for the assistant (the chat endpoint has no job field, so it travels as a message).
  String assistantPreamble() {
    final jd = text.trim();
    final clipped = jd.length > 2600 ? '${jd.substring(0, 2600)}...' : jd;
    return 'I am looking at this job. Role: ${title.isEmpty ? 'unknown' : title}. Company: ${company.isEmpty ? 'unknown' : company}.'
        '${location == null ? '' : ' Location: $location.'}'
        '${score == null ? '' : ' My match: ${score!.round()}%.'}'
        ' Job text:\n$clipped\n\nAnswer my next questions about this job using only my verified profile facts. Never invent anything about me.';
  }
}

// ------------------------------------------------------------------ cleaning

final _chrome = <RegExp>[
  RegExp(r'^(like|comment|repost|send|share|follow|following|connect|message|save|saved|apply|easy apply|promoted|visit|reply|more|see more|show more|\+ ?follow)$', caseSensitive: false),
  RegExp(r'^(like|comment|repost|send|share)([\s|·•\-]+(like|comment|repost|send|share|reply))+$', caseSensitive: false),
  RegExp(r'^[\d.,]+\s*[kKmM]?\s*(likes?|comments?|reposts?|reactions?|shares?|followers?|connections?|views?|impressions?|applicants?|clicks?|replies)(\s*[·•].*)?$', caseSensitive: false),
  RegExp(r'^\d+\s*(s|m|min|h|hr|d|w|wk|mo|yr|y)\s*[·•]?\s*(edited)?\s*[·•]?\s*(\S{0,3})$', caseSensitive: false),
  RegExp(r'^(\d+(st|nd|rd|th)\+?|[·•]\s*(1st|2nd|3rd\+?))$', caseSensitive: false),
  RegExp(r'^[…\.]{0,3}\s*(see|show)?\s*more$', caseSensitive: false),
  RegExp(r'^(most relevant|add a comment\.*|write a message\.*|be the first to .*|react|\d+ more repl(y|ies))$', caseSensitive: false),
  RegExp(r'^[\W\d_]{0,4}$'), // lone icons, bullets, stray digits
];

final _chromeInline = RegExp(r'\b(Like|Comment|Repost|Send)\s*(?:[·•|]\s*)?(?=(Like|Comment|Repost|Send)\b)');

/// Drops UI chrome and OCR noise ("Like Comment Repost Send", counters, "2d •", "...see more"), repairs split e-mail
/// addresses and tidies whitespace. Keeps every line that could be part of the job.
String cleanJobText(String raw) {
  var t = raw.replaceAll('\r', '').replaceAll('\u00a0', ' ');
  t = t.replaceAllMapped(RegExp(r'\s*[\[(]\s*at\s*[\])]\s*', caseSensitive: false), (_) => '@');
  t = t.replaceAllMapped(RegExp(r'\s*[\[(]\s*dot\s*[\])]\s*', caseSensitive: false), (_) => '.');
  // "name @ gmail . com" -> "name@gmail.com"
  t = t.replaceAllMapped(
    RegExp(r'([A-Za-z0-9._%+\-]+)[ \t]*@[ \t]*([A-Za-z0-9\-]+(?:[ \t]*\.[ \t]*[A-Za-z0-9\-]+)*[ \t]*\.[ \t]*[A-Za-z]{2,6})\b'),
    (m) => '${m[1]}@${m[2]!.replaceAll(RegExp(r'\s+'), '')}',
  );
  final out = <String>[];
  for (var line in t.split('\n')) {
    line = line.replaceAll(_chromeInline, '').replaceAll(RegExp(r'[ \t]+'), ' ').trim();
    if (line.isEmpty) {
      if (out.isNotEmpty && out.last.isNotEmpty) out.add('');
      continue;
    }
    if (_chrome.any((r) => r.hasMatch(line))) continue;
    if (out.isNotEmpty && out.last == line) continue; // doubled lines from overlapping text blocks
    out.add(line);
  }
  while (out.isNotEmpty && out.last.isEmpty) {
    out.removeLast();
  }
  return out.join('\n');
}

// ------------------------------------------------------------------ extraction

final _emailRe = RegExp(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}');
final _skipMail = RegExp(r'^(noreply|no-reply|donotreply|notifications?|jobs-listings)', caseSensitive: false);

/// E-mail addresses in the text, the likely application address (careers@, hr@, jobs@...) first.
List<String> extractEmails(String text) {
  final seen = <String>[];
  for (final m in _emailRe.allMatches(text)) {
    final e = m.group(0)!.toLowerCase().replaceAll(RegExp(r'[.\-_]+$'), '');
    if (_skipMail.hasMatch(e) || e.endsWith('.png') || e.endsWith('.jpg')) continue;
    if (!seen.contains(e)) seen.add(e);
  }
  const rank = ['career', 'hr', 'job', 'talent', 'hiring', 'recruit', 'resume', 'cv'];
  final first = [for (final e in seen) if (rank.any((r) => e.split('@').first.contains(r))) e];
  return [...first, for (final e in seen) if (!first.contains(e)) e];
}

const _cities = ['Bengaluru', 'Bangalore', 'Hyderabad', 'Pune', 'Chennai', 'Mumbai', 'Delhi', 'New Delhi', 'Noida', 'Gurgaon', 'Gurugram', 'Kolkata', 'Ahmedabad', 'Kochi', 'Coimbatore', 'Remote', 'Hybrid', 'Work from home'];

String? extractLocation(String text) {
  final m = RegExp(r'(?:location|work location|based in|work from|locations?)\s*[:\-–]\s*([^\n|]{2,60})', caseSensitive: false).firstMatch(text);
  if (m != null) return m.group(1)!.trim().replaceAll(RegExp(r'[.\s]+$'), '');
  final found = [for (final c in _cities) if (RegExp('\\b${RegExp.escape(c)}\\b', caseSensitive: false).hasMatch(text)) c];
  return found.isEmpty ? null : found.take(2).join(', ');
}

const _roleNoun = r'(?:engineer|developer|sdet|tester|analyst|manager|lead|architect|consultant|specialist|scientist|designer|administrator|associate|intern|executive|officer|programmer|qa|qe|devops|sre)';

String _tidy(String s) =>
    s.replaceAll(RegExp(r'[*#_]+'), '').replaceAll(RegExp(r'\s+'), ' ').trim().replaceAll(RegExp(r'^[\s:\-–|]+|[\s.,:;!\-–|]+$'), '');

/// Best-effort role and company from a job post or hiring-post screenshot. The server's /studio/detect fills what this misses.
({String title, String company}) guessRoleCompany(String text) {
  var title = '';
  var company = '';
  final labelled = RegExp(r'(?:job title|role|position|designation|hiring for|vacancy)\s*[:\-–]\s*([^\n|]{3,70})', caseSensitive: false).firstMatch(text);
  if (labelled != null) title = _tidy(labelled.group(1)!);
  if (title.isEmpty) {
    final hiring = RegExp(
      r'(?:hiring|looking for|seeking|recruiting)\s*(?:for\s*)?(?:an?\s+|the\s+)?([A-Za-z][A-Za-z0-9+/&.#\- ]{1,55}?\b' + _roleNoun + r'\b[A-Za-z0-9+/&.#\- ]{0,20}?)(?=\s+(?:at|@|for|with|in|to)\b|[.,\n!|(]|$)',
      caseSensitive: false,
    ).firstMatch(text);
    if (hiring != null) title = _tidy(hiring.group(1)!);
  }
  if (title.isEmpty) {
    final noun = RegExp(r'\b' + _roleNoun + r'\b', caseSensitive: false);
    for (final line in text.split('\n')) {
      final l = line.trim();
      if (l.length < 60 && noun.hasMatch(l) && !l.contains('@')) {
        title = _tidy(l);
        break;
      }
    }
  }
  final co = RegExp(r'(?:company|organi[sz]ation|employer)\s*[:\-–]\s*([^\n|]{2,60})', caseSensitive: false).firstMatch(text);
  if (co != null) {
    company = _tidy(co.group(1)!);
  } else {
    final at = RegExp(r'(?:hiring|opening|opportunity|vacancy|role|position|join(?:ing)?|work(?:ing)? (?:with|at))[^\n]{0,60}?\b(?:at|@|with)\s+([A-Z][A-Za-z0-9&.\-]*(?:\s+[A-Z][A-Za-z0-9&.\-]*){0,3})').firstMatch(text);
    if (at != null) company = _tidy(at.group(1)!);
  }
  if (company.isEmpty) {
    final mail = extractEmails(text).where((e) => !RegExp(r'@(gmail|yahoo|outlook|hotmail|rediffmail|proton|icloud)\.').hasMatch(e));
    if (mail.isNotEmpty) {
      final host = mail.first.split('@').last.split('.').first;
      company = host.isEmpty ? '' : host[0].toUpperCase() + host.substring(1);
    }
  }
  return (title: title.length > 80 ? title.substring(0, 80) : title, company: company);
}

/// Builds a full [JobContext] from raw (OCR or shared) text.
JobContext jobContextFromText(String raw, {String? link}) {
  final text = cleanJobText(raw);
  final rc = guessRoleCompany(text);
  return JobContext(title: rc.title, company: rc.company, text: text, location: extractLocation(text), link: link, emails: extractEmails(text));
}

// ------------------------------------------------------------------ OCR

/// On-device text recognition (ML Kit, Latin script): the image never leaves the phone. Returns the cleaned text,
/// or null when nothing could be read.
Future<String?> readImageText(String path) async {
  final rec = TextRecognizer(script: TextRecognitionScript.latin);
  try {
    final r = await rec.processImage(InputImage.fromFilePath(path));
    final text = cleanJobText(r.text);
    return text.isEmpty ? null : text;
  } catch (_) {
    return null;
  } finally {
    await rec.close();
  }
}
