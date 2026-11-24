import 'package:flutter_test/flutter_test.dart';
import 'package:saige_mobile/core/briefing_logic.dart';

void main() {
  // 2026-11-25 03:30 UTC = 09:00 IST
  final now = DateTime.utc(2026, 11, 25, 3, 30);

  group('briefing assembly', () {
    test('builds rows from real data only and picks one suggestion', () {
      final b = assembleBriefing(
        now: now,
        matches: [
          {'id': 'a', 'title': 'SDET', 'company': 'Acme', 'score': 82},
          {'id': 'b', 'title': 'QA', 'company': 'Beta', 'score': 40},
        ],
        interviews: [
          {'interview_id': 'i1', 'company': 'Zeta', 'round': 'Round 1', 'scheduled_at': DateTime.utc(2026, 11, 25, 9).toIso8601String()},
          {'interview_id': 'i2', 'company': 'Far', 'scheduled_at': DateTime.utc(2026, 12, 20).toIso8601String()},
        ],
        replies: [
          {'id': 'r1', 'status': 'replied', 'company': 'Gamma', 'snippet': 'Can we talk?'},
          {'id': 'r2', 'status': 'bounced', 'company': 'Bad'},
        ],
        approvals: 2,
        streak: {'current': 4, 'goal_met': false},
      );
      final kinds = b.items.map((e) => e.kind).toList();
      expect(kinds, ['interview', 'reply', 'approvals', 'matches', 'streak']);
      expect(b.items.first.title, 'Zeta today at 2:30 PM');
      expect(b.items.first.route, 'warroom:i1');
      expect(b.items[1].route, 'reply:r1'); // a bounce is not a reply
      expect(b.items[3].sub, contains('SDET at Acme (82%)'));
      expect(b.suggestion!.route, 'warroom:i1'); // interview today beats everything
      expect(b.streak, 4);
    });

    test('empty data gives an empty briefing and no suggestion', () {
      expect(assembleBriefing(now: now).isEmpty, isTrue);
    });

    test('matches already seen are not new; streak suggestion when nothing else', () {
      final b = assembleBriefing(
        now: now,
        matches: [
          {'id': 'a', 'title': 'SDET', 'company': 'Acme', 'score': 90}
        ],
        seenMatchIds: {'a'},
        streak: {'current': 3, 'goal_met': false},
      );
      expect(b.items.map((e) => e.kind), ['streak']);
      expect(b.suggestion!.title, contains('3-day streak'));
    });

    test('tomorrow interview shows but is not the urgent suggestion', () {
      final b = assembleBriefing(now: now, interviews: [
        {'id': 'x', 'company': 'Next', 'scheduled_at': DateTime.utc(2026, 11, 26, 5).toIso8601String()}
      ]);
      expect(b.items.single.title, startsWith('Next tomorrow'));
      expect(b.suggestion, isNull);
    });

    test('notification text', () {
      final b = assembleBriefing(now: now, approvals: 1, streak: {'current': 2});
      final (t, body) = briefingNotificationText(b, name: 'Asha Rao');
      expect(t, 'Good morning, Asha');
      expect(body, contains('1 item waiting for you'));
      expect(body, contains('2-day streak'));
    });

    test('excludeSeen keeps new matches of the same day visible', () {
      expect(excludeSeen(seen: {'a', 'b'}, newToday: {'b'}, newDay: '2026-11-25', today: '2026-11-25'), {'a'});
      expect(excludeSeen(seen: {'a', 'b'}, newToday: {'b'}, newDay: '2026-11-24', today: '2026-11-25'), {'a', 'b'});
    });
  });

  group('once-per-day guard (IST)', () {
    test('default time is 8:30 IST', () => expect(clockLabel(defaultBriefingMinutes), '8:30 AM'));

    test('not before the set time', () {
      final early = DateTime.utc(2026, 11, 25, 2, 59); // 08:29 IST
      expect(shouldShowBriefing(nowUtc: early, enabled: true, minutes: defaultBriefingMinutes), isFalse);
    });
    test('shows after the set time, once per IST day', () {
      final t = DateTime.utc(2026, 11, 25, 3, 0); // 08:30 IST
      expect(shouldShowBriefing(nowUtc: t, enabled: true, minutes: defaultBriefingMinutes), isTrue);
      expect(shouldShowBriefing(nowUtc: t, enabled: true, minutes: defaultBriefingMinutes, lastDay: istDay(t)), isFalse);
      expect(shouldShowBriefing(nowUtc: t, enabled: true, minutes: defaultBriefingMinutes, lastDay: '2026-11-24'), isTrue);
    });
    test('off, or after the morning window, never shows', () {
      final t = DateTime.utc(2026, 11, 25, 3, 0);
      expect(shouldShowBriefing(nowUtc: t, enabled: false, minutes: defaultBriefingMinutes), isFalse);
      final late = DateTime.utc(2026, 11, 25, 12, 0); // 17:30 IST
      expect(shouldShowBriefing(nowUtc: late, enabled: true, minutes: defaultBriefingMinutes), isFalse);
    });
    test('IST date rolls over at 18:30 UTC', () {
      expect(istDay(DateTime.utc(2026, 11, 25, 18, 29)), '2026-11-25');
      expect(istDay(DateTime.utc(2026, 11, 25, 18, 30)), '2026-11-26');
    });
  });

  group('interview reminders', () {
    test('schedules 24h and 1h before, in UTC', () {
      final at = DateTime.utc(2026, 11, 27, 10);
      final s = reminderSlots('i1', at, now);
      expect(s.length, 2);
      expect(s[0].kind, ReminderKind.dayBefore);
      expect(s[0].at, DateTime.utc(2026, 11, 26, 10));
      expect(s[1].at, DateTime.utc(2026, 11, 27, 9));
      expect(s[0].id, isNot(s[1].id));
      expect(s[0].id, reminderId('i1', ReminderKind.dayBefore)); // stable
    });
    test('past slots are dropped', () {
      final at = DateTime.utc(2026, 11, 25, 10); // 6.5h away: only the 1h reminder is ahead
      expect(reminderSlots('i1', at, now).map((e) => e.kind), [ReminderKind.hourBefore]);
      expect(reminderSlots('i1', DateTime.utc(2026, 11, 25, 3, 40), now), isEmpty);
    });
    test('slots from war-room rows skip bad rows; text names the IST time', () {
      final rows = [
        {'interview_id': 'a', 'scheduled_at': DateTime.utc(2026, 12, 1, 4).toIso8601String(), 'company': 'Acme'},
        {'interview_id': '', 'scheduled_at': 'x'},
      ];
      expect(slotsForInterviews(rows, now).length, 2);
      final (t, b) = reminderText(ReminderKind.hourBefore, 'Acme', 'Round 2', DateTime.utc(2026, 12, 1, 4));
      expect(t, 'Interview in 1 hour');
      expect(b, contains('Acme interview (Round 2) starts at 9:30 AM IST'));
    });
  });
}
