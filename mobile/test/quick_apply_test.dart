import 'package:material_ui/material_ui.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:saige_mobile/features/jobchat/email_draft.dart';
import 'package:saige_mobile/features/quickapply/quick_apply_logic.dart';
import 'package:saige_mobile/features/reply/reply_logic.dart';

void main() {
  test('deck drops skipped and handled jobs, best score first, no duplicates', () {
    final radar = [
      {'id': '1', 'score': 60},
      {'id': '2', 'score': 90},
      {'id': '3', 'score': 70},
      {'id': '2', 'score': 90},
      {'id': '4', 'score': 80},
    ];
    expect(buildDeck(radar, skipped: {'3'}, handled: {'4'}).map((e) => e['id']), ['2', '1']);
  });

  test('tray round trip and state', () {
    final a = ReadyItem(jobId: 'a', title: 'SDET', company: 'Acme', resumeId: 'r1', to: 'hr@acme.com', subject: 's', body: 'b');
    final b = ReadyItem(jobId: 'b', title: 'QA', company: 'Beta', resumeId: 'r2');
    final c = ReadyItem(jobId: 'c', title: 'Dev', company: 'Cee', needsDetails: true);
    final back = decodeTray(encodeTray([a, b, c]));
    expect(back.map((e) => e.state), ['ready', 'no_email', 'needs_details']);
    expect(back.first.to, 'hr@acme.com');
    expect(decodeTray('not json'), isEmpty);
    expect(decodeTray(null), isEmpty);
  });

  test('capIds keeps the newest', () => expect(capIds(['a', 'b', 'c'], max: 2), ['b', 'c']));

  test('thin JD text is long enough for the backend minimum', () {
    final t = thinJdText({'title': 'SDET', 'company': 'Acme', 'location': 'Pune', 'matched_skills': ['Selenium'], 'missing_skills': ['Go']});
    expect(t.length, greaterThan(30));
    expect(t, contains('Selenium'));
  });

  test('reply draft is matched by recruiter address, then company', () {
    final drafts = [
      {'kind': 'followup', 'status': 'draft', 'mailto': 'mailto:hr@acme.com?x=1', 'company': 'Acme'},
      {'kind': 'reply', 'status': 'draft', 'mailto': 'mailto:Hr@Acme.com?subject=Re', 'company': 'Acme', 'id': 'd1'},
      {'kind': 'reply', 'status': 'draft', 'mailto': null, 'company': 'Beta', 'id': 'd2'},
      {'kind': 'reply', 'status': 'sent', 'mailto': 'mailto:hr@acme.com', 'company': 'Acme', 'id': 'd3'},
    ];
    expect(matchReplyDraft(drafts, {'to': 'hr@acme.com'})!['id'], 'd1');
    expect(matchReplyDraft(drafts, {'to': 'nobody@x.com', 'company': 'beta'})!['id'], 'd2');
    expect(matchReplyDraft(drafts, {'to': 'nobody@x.com', 'company': 'Zed'}), isNull);
  });

  group('one-tap send with Undo', () {
    Future<SendOutcome?> run(WidgetTester t, {required bool undo, required List<String> calls}) async {
      SendOutcome? result;
      await t.pumpWidget(MaterialApp(
        home: Scaffold(
          body: Builder(
            builder: (c) => Center(
              child: TextButton(
                onPressed: () async => result = await sendWithUndo(c, label: 'Sending...', send: () async {
                  calls.add('sent');
                  return null;
                }),
                child: const Text('go'),
              ),
            ),
          ),
        ),
      ));
      await t.tap(find.text('go'));
      await t.pump();
      await t.pump(const Duration(milliseconds: 400));
      expect(find.text('Undo'), findsOneWidget);
      if (undo) {
        await t.tap(find.text('Undo'));
      }
      for (var i = 0; i < 12; i++) {
        await t.pump(const Duration(seconds: 1));
      }
      await t.pumpAndSettle();
      return result;
    }

    testWidgets('sends after the Undo window', (t) async {
      final calls = <String>[];
      final r = await run(t, undo: false, calls: calls);
      expect(calls, ['sent']);
      expect(r!.sent, isTrue);
    });

    testWidgets('Undo cancels the send', (t) async {
      final calls = <String>[];
      final r = await run(t, undo: true, calls: calls);
      expect(calls, isEmpty);
      expect(r!.undone, isTrue);
    });
  });
}
