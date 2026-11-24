// Pure helpers for the Reply assistant.

String _mailFrom(String mailto) {
  final m = RegExp(r'^mailto:([^?]+)').firstMatch(mailto);
  return m == null ? '' : Uri.decodeComponent(m.group(1)!).trim().toLowerCase();
}

/// Picks the backend's reply draft (outreach kind "reply", status draft) for a recruiter reply from the pulse.
/// The outreach list does not expose the inbound email id, so the match is by the recruiter's address (the contact the
/// draft is addressed to), then by company. Drafts come newest first, so the first hit wins. Returns null when none matches.
Map<String, dynamic>? matchReplyDraft(List<Map<String, dynamic>> outreach, Map<String, dynamic> reply) {
  final drafts = [for (final o in outreach) if (o['kind'] == 'reply' && o['status'] == 'draft') o];
  final to = '${reply['to'] ?? ''}'.trim().toLowerCase();
  if (to.isNotEmpty) {
    for (final d in drafts) {
      if (_mailFrom('${d['mailto'] ?? ''}') == to) return d;
    }
  }
  final company = '${reply['company'] ?? ''}'.trim().toLowerCase();
  if (company.isNotEmpty) {
    for (final d in drafts) {
      if ('${d['company'] ?? ''}'.trim().toLowerCase() == company) return d;
    }
  }
  return null;
}
