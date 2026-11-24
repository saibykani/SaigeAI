import 'dart:convert';

/// Pure logic for Quick apply: the deck of cards, the skipped list and the "Ready to send" tray.

/// One prepared application waiting in the tray. Nothing here is sent until the user reviews it and taps Send.
class ReadyItem {
  ReadyItem({
    required this.jobId,
    required this.title,
    required this.company,
    this.url = '',
    this.score,
    this.resumeId,
    this.to = '',
    this.subject = '',
    this.body = '',
    this.from,
    this.suggestions = const [],
    this.needsDetails = false,
    this.careerJobId,
    this.jdText = '',
    this.location,
    DateTime? at,
  }) : at = at ?? DateTime.now();

  final String jobId; // radar id
  final String title;
  final String company;
  final String url;
  final num? score;
  final String? resumeId;
  String to;
  String subject;
  String body;
  final String? from;
  final List<String> suggestions;
  final bool needsDetails; // the backend needs facts only the user can give; finish it in the job chat
  final String? careerJobId;
  final String jdText;
  final String? location;
  final DateTime at;

  bool get hasEmail => to.trim().isNotEmpty;
  bool get hasResume => resumeId != null && resumeId!.isNotEmpty;

  /// ready: can be reviewed and sent. noEmail: only "Open job" + resume download (or add an address while reviewing).
  String get state => needsDetails ? 'needs_details' : (hasEmail ? 'ready' : 'no_email');

  Map<String, dynamic> toJson() => {
        'jobId': jobId, 'title': title, 'company': company, 'url': url, 'score': score, 'resumeId': resumeId, 'to': to, 'subject': subject,
        'body': body, 'from': from, 'suggestions': suggestions, 'needsDetails': needsDetails, 'careerJobId': careerJobId, 'jdText': jdText,
        'location': location, 'at': at.toIso8601String(),
      };

  factory ReadyItem.fromJson(Map<String, dynamic> j) => ReadyItem(
        jobId: '${j['jobId']}',
        title: '${j['title'] ?? ''}',
        company: '${j['company'] ?? ''}',
        url: '${j['url'] ?? ''}',
        score: j['score'] as num?,
        resumeId: j['resumeId'] as String?,
        to: '${j['to'] ?? ''}',
        subject: '${j['subject'] ?? ''}',
        body: '${j['body'] ?? ''}',
        from: j['from'] as String?,
        suggestions: [for (final e in (j['suggestions'] as List? ?? const [])) '$e'],
        needsDetails: j['needsDetails'] == true,
        careerJobId: j['careerJobId'] as String?,
        jdText: '${j['jdText'] ?? ''}',
        location: j['location'] as String?,
        at: DateTime.tryParse('${j['at']}'),
      );
}

String encodeTray(List<ReadyItem> items) => jsonEncode([for (final i in items) i.toJson()]);

List<ReadyItem> decodeTray(String? raw) {
  if (raw == null || raw.isEmpty) return [];
  try {
    return [for (final e in jsonDecode(raw) as List) ReadyItem.fromJson(Map<String, dynamic>.from(e as Map))];
  } catch (_) {
    return [];
  }
}

/// Radar items still worth showing: not skipped, not already in the tray or sent, best score first.
List<Map<String, dynamic>> buildDeck(List<Map<String, dynamic>> radar, {Set<String> skipped = const {}, Set<String> handled = const {}}) {
  final seen = <String>{};
  final out = [
    for (final j in radar)
      if (!skipped.contains('${j['id']}') && !handled.contains('${j['id']}') && seen.add('${j['id']}')) j,
  ];
  out.sort((a, b) => ((b['score'] as num?) ?? 0).compareTo((a['score'] as num?) ?? 0));
  return out;
}

/// Keeps a remembered-ids list short (newest last).
List<String> capIds(Iterable<String> ids, {int max = 500}) {
  final l = ids.toList();
  return l.length > max ? l.sublist(l.length - max) : l;
}

/// A short JD text for a feed job (no description on the radar): enough for the backend's 30-character minimum and the
/// skills match. The tailored resume still only uses the verified profile.
String thinJdText(Map<String, dynamic> j) {
  final matched = (j['matched_skills'] as List? ?? const []).map((e) => '$e').toList();
  final missing = (j['missing_skills'] as List? ?? const []).map((e) => '$e').toList();
  return [
    '${j['title']} at ${j['company']}. ${j['location'] ?? ''}'.trim(),
    if (matched.isNotEmpty) 'Skills asked for: ${matched.join(', ')}.',
    if (missing.isNotEmpty) 'Also asked for: ${missing.join(', ')}.',
  ].join('\n');
}
