import 'package:flutter_test/flutter_test.dart';
import 'package:saige_mobile/features/jobchat/email_draft.dart';
import 'package:saige_mobile/features/jobchat/job_context.dart';
import 'package:saige_mobile/core/api.dart';

const _post = '''
Priya Sharma
Talent Acquisition at Acme Tech
2d •
We are hiring a Senior QA Engineer at Acme Tech!
Location: Bengaluru
Skills: Selenium, Java, API testing
Send your resume to careers @ acmetech . com
...see more
1,245 likes
34 comments
Like Comment Repost Send
Like
Comment
Repost
''';

void main() {
  test('cleanJobText drops LinkedIn chrome and repairs the email', () {
    final t = cleanJobText(_post);
    expect(t, isNot(contains('Like')));
    expect(t, isNot(contains('Repost')));
    expect(t, isNot(contains('1,245')));
    expect(t, isNot(contains('see more')));
    expect(t, isNot(contains('2d')));
    expect(t, contains('careers@acmetech.com'));
    expect(t, contains('Senior QA Engineer'));
  });

  test('extracts role, company, location and emails', () {
    final c = jobContextFromText(_post);
    expect(c.title.toLowerCase(), contains('qa engineer'));
    expect(c.company, 'Acme Tech');
    expect(c.location, 'Bengaluru');
    expect(c.emails, ['careers@acmetech.com']);
    expect(c.hasJd, isTrue);
  });

  test('application addresses are ranked first and noise is skipped', () {
    expect(extractEmails('ping bob@gmail.com or hr@x.io, noreply@x.io'), ['hr@x.io', 'bob@gmail.com']);
  });

  test('jdBody prefers ids over pasted text', () {
    expect(JobContext(text: 'x' * 40, careerJobId: 'c1', title: 'T', company: 'C').jdBody().containsKey('career_job_id'), isTrue);
    expect(JobContext(text: 'x' * 40).jdBody()['jd_text'], 'x' * 40);
  });

  test('send errors are friendly', () {
    expect(sendErrorText(ApiException('Recruiter outreach is paused.', status: 423)), contains('paused'));
    expect(sendErrorText(ApiException('Connect Gmail with an App Password', status: 409)), contains('Connect Gmail'));
    expect(sendErrorText(ApiException('Daily outreach limit reached (10).', status: 429)), contains('limit'));
    expect(sendErrorText(ApiException('x', status: 422)), contains('verified profile'));
    expect(validEmail('a@b.co'), isTrue);
    expect(validEmail('nope'), isFalse);
  });
}
