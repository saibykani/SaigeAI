// Pure logic for the morning briefing and interview reminders (no Flutter, no network), so it can be unit tested.

const istOffset = Duration(hours: 5, minutes: 30);

DateTime toIst(DateTime t) => t.toUtc().add(istOffset);

String istDay(DateTime t) {
  final i = toIst(t);
  return '${i.year}-${i.month.toString().padLeft(2, '0')}-${i.day.toString().padLeft(2, '0')}';
}

/// Minutes since midnight, IST.
int istMinutes(DateTime t) {
  final i = toIst(t);
  return i.hour * 60 + i.minute;
}

const defaultBriefingMinutes = 8 * 60 + 30; // 8:30 IST
const briefingWindowMinutes = 6 * 60; // a morning briefing is not shown after the morning is over

String clockLabel(int minutes) {
  final h = (minutes ~/ 60) % 24;
  final m = minutes % 60;
  final h12 = h % 12 == 0 ? 12 : h % 12;
  return '$h12:${m.toString().padLeft(2, '0')} ${h < 12 ? 'AM' : 'PM'}';
}

/// Once-per-day guard: true when the briefing is on, the set time (IST) has passed, the morning window is still open
/// and it has not been shown for today's IST date yet.
bool shouldShowBriefing({required DateTime nowUtc, required bool enabled, required int minutes, String? lastDay}) {
  if (!enabled) return false;
  final now = istMinutes(nowUtc);
  if (now < minutes || now > minutes + briefingWindowMinutes) return false;
  return lastDay != istDay(nowUtc);
}

/// One tappable row of the briefing. [route] is one of: radar, quickapply, warroom, warroom:ID, reply:ID, approvals, streak.
class BriefingItem {
  const BriefingItem({required this.kind, required this.title, required this.sub, required this.route});
  final String kind; // matches | interview | reply | approvals | streak | suggest
  final String title;
  final String sub;
  final String route;
}

class Briefing {
  const Briefing({required this.items, this.suggestion, required this.streak});
  final List<BriefingItem> items;
  final BriefingItem? suggestion;
  final int streak;
  bool get isEmpty => items.isEmpty && suggestion == null;
}

const strongMatch = 60;

List<Map<String, dynamic>> _maps(dynamic v) => v is List ? [for (final e in v) if (e is Map) Map<String, dynamic>.from(e)] : <Map<String, dynamic>>[];

/// Where an interview falls relative to now, in IST days: 0 = today, 1 = tomorrow, anything else = null.
int? interviewDayOffset(DateTime at, DateTime now) {
  final a = DateTime.parse(istDay(at));
  final n = DateTime.parse(istDay(now));
  final d = a.difference(n).inDays;
  return d == 0 || d == 1 ? d : null;
}

/// Match ids that count as "already seen" for [today]'s briefing: everything seen before, except what was first shown today
/// (so reopening the screen later the same day still lists today's new matches).
Set<String> excludeSeen({required Set<String> seen, required Set<String> newToday, String? newDay, required String today}) =>
    newDay == today ? seen.difference(newToday) : seen;

/// Builds the briefing from real records only. Inputs are the raw API maps (radar items, war-room interviews, pulse
/// replies, approvals, streak). Nothing is invented: a section with no data is left out.
Briefing assembleBriefing({
  required DateTime now,
  List<dynamic> matches = const [],
  List<dynamic> interviews = const [],
  List<dynamic> replies = const [],
  int approvals = 0,
  Map<String, dynamic>? streak,
  Set<String> seenMatchIds = const {},
}) {
  final items = <BriefingItem>[];
  BriefingItem? suggest;

  // interviews today / tomorrow, soonest first
  final upcoming = <(DateTime, Map<String, dynamic>, int)>[];
  for (final i in _maps(interviews)) {
    final at = DateTime.tryParse('${i['scheduled_at']}');
    if (at == null || at.isBefore(now.subtract(const Duration(hours: 1)))) continue;
    final off = interviewDayOffset(at, now);
    if (off != null) upcoming.add((at, i, off));
  }
  upcoming.sort((a, b) => a.$1.compareTo(b.$1));
  for (final (at, i, off) in upcoming) {
    final id = '${i['interview_id'] ?? i['id'] ?? ''}';
    final who = '${i['company'] ?? 'Interview'}';
    final round = '${i['round'] ?? i['role'] ?? ''}'.trim();
    items.add(BriefingItem(
      kind: 'interview',
      title: '$who ${off == 0 ? 'today' : 'tomorrow'} at ${clockLabel(istMinutes(at))}',
      sub: round.isEmpty ? 'Open the war room to prep' : '$round. Open the war room to prep',
      route: id.isEmpty ? 'warroom' : 'warroom:$id',
    ));
  }

  // new recruiter replies (not bounces)
  final real = [for (final r in _maps(replies)) if (r['status'] != 'bounced') r];
  for (final r in real.take(3)) {
    final who = '${r['company'] ?? r['to'] ?? 'a recruiter'}';
    items.add(BriefingItem(kind: 'reply', title: 'Reply from $who', sub: '${r['snippet'] ?? r['subject'] ?? 'Tap to read and answer'}'.trim(), route: 'reply:${r['id']}'));
  }
  if (real.length > 3) {
    items.add(BriefingItem(kind: 'reply', title: '${real.length - 3} more recruiter replies', sub: 'Open drafts and approvals', route: 'approvals'));
  }

  if (approvals > 0) {
    items.add(BriefingItem(kind: 'approvals', title: '$approvals ${approvals == 1 ? 'item' : 'items'} waiting for you', sub: 'Review, then send. Nothing goes out without your tap', route: 'approvals'));
  }

  // new top matches (score >= strongMatch, not shown in a previous briefing)
  final fresh = [for (final m in _maps(matches)) if (((m['score'] as num?) ?? 0) >= strongMatch && !seenMatchIds.contains('${m['id']}')) m]
    ..sort((a, b) => ((b['score'] as num?) ?? 0).compareTo((a['score'] as num?) ?? 0));
  if (fresh.isNotEmpty) {
    final top = fresh.first;
    items.add(BriefingItem(
      kind: 'matches',
      title: '${fresh.length} new top ${fresh.length == 1 ? 'match' : 'matches'}',
      sub: '${top['title']} at ${top['company']} (${((top['score'] as num?) ?? 0).round()}%)${fresh.length > 1 ? ' and ${fresh.length - 1} more' : ''}',
      route: 'radar',
    ));
  }

  final cur = ((streak?['current']) as num?)?.toInt() ?? 0;
  final goalMet = streak?['goal_met'] == true;
  if (cur > 0) {
    items.add(BriefingItem(
      kind: 'streak',
      title: '$cur-day streak',
      sub: goalMet ? "Today's goal is done" : 'One action today keeps it going',
      route: 'streak',
    ));
  }

  // one suggested action, in order of urgency
  if (upcoming.isNotEmpty && upcoming.first.$3 == 0) {
    final i = upcoming.first.$2;
    final id = '${i['interview_id'] ?? i['id'] ?? ''}';
    suggest = BriefingItem(kind: 'suggest', title: 'Do a 5-minute voice practice', sub: 'Before your ${i['company'] ?? 'interview'} interview today', route: id.isEmpty ? 'warroom' : 'warroom:$id');
  } else if (real.isNotEmpty) {
    suggest = BriefingItem(kind: 'suggest', title: 'Answer ${real.first['company'] ?? 'the recruiter'}', sub: 'Quick replies get better responses', route: 'reply:${real.first['id']}');
  } else if (approvals > 0) {
    suggest = BriefingItem(kind: 'suggest', title: 'Clear your approvals', sub: 'Review and send what is ready', route: 'approvals');
  } else if (fresh.isNotEmpty) {
    suggest = BriefingItem(kind: 'suggest', title: 'Swipe through your top matches', sub: 'Prepare resumes and emails in one go', route: 'quickapply');
  } else if (cur > 0 && !goalMet) {
    suggest = BriefingItem(kind: 'suggest', title: 'Keep your $cur-day streak', sub: 'Apply to one job or message one recruiter', route: 'quickapply');
  }
  return Briefing(items: items, suggestion: suggest, streak: cur);
}

/// Notification text for the briefing: a short title and up to 4 lines.
(String, String) briefingNotificationText(Briefing b, {String name = ''}) {
  final title = name.trim().isEmpty || name.trim() == 'there' ? 'Good morning' : 'Good morning, ${name.trim().split(' ').first}';
  final lines = [for (final i in b.items.where((e) => e.kind != 'streak').take(4)) i.title];
  if (b.suggestion != null) lines.add('Next: ${b.suggestion!.title}');
  if (b.streak > 0) lines.add('${b.streak}-day streak');
  return (title, lines.join('\n'));
}

// ------------------------------------------------------------------ interview reminders

enum ReminderKind { dayBefore, hourBefore }

class ReminderSlot {
  const ReminderSlot({required this.id, required this.interviewId, required this.kind, required this.at});
  final int id;
  final String interviewId;
  final ReminderKind kind;
  final DateTime at; // UTC
}

/// Stable 31-bit id per (interview, kind) so a reminder can be rescheduled or cancelled later.
int reminderId(String interviewId, ReminderKind kind) {
  var h = 2166136261;
  for (final c in '${kind.name}|$interviewId'.codeUnits) {
    h = ((h ^ c) * 16777619) & 0x7fffffff;
  }
  return h;
}

/// The reminders to schedule for one interview: 24 h and 1 h before. Slots already in the past are dropped.
List<ReminderSlot> reminderSlots(String interviewId, DateTime at, DateTime now) {
  final out = <ReminderSlot>[];
  for (final (kind, before) in [(ReminderKind.dayBefore, const Duration(hours: 24)), (ReminderKind.hourBefore, const Duration(hours: 1))]) {
    final when = at.toUtc().subtract(before);
    if (when.isAfter(now.toUtc().add(const Duration(seconds: 30)))) out.add(ReminderSlot(id: reminderId(interviewId, kind), interviewId: interviewId, kind: kind, at: when));
  }
  return out;
}

/// All slots for a list of interviews (war-room rows or interview rows).
List<ReminderSlot> slotsForInterviews(List<dynamic> interviews, DateTime now) {
  final out = <ReminderSlot>[];
  for (final i in _maps(interviews)) {
    final id = '${i['interview_id'] ?? i['id'] ?? ''}';
    final at = DateTime.tryParse('${i['scheduled_at']}');
    if (id.isEmpty || at == null) continue;
    out.addAll(reminderSlots(id, at, now));
  }
  return out;
}

(String, String) reminderText(ReminderKind kind, String company, String round, DateTime at) {
  final who = company.trim().isEmpty ? 'your interview' : '$company interview';
  final r = round.trim().isEmpty ? '' : ' ($round)';
  return kind == ReminderKind.hourBefore
      ? ('Interview in 1 hour', 'Your $who$r starts at ${clockLabel(istMinutes(at))} IST. Open the war room for a last look.')
      : ('Interview tomorrow', 'Your $who$r is at ${clockLabel(istMinutes(at))} IST. Try a 5-minute voice practice in the war room.');
}
