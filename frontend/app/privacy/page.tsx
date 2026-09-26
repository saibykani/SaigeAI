import type { Metadata } from "next";

import { CONTACT_EMAIL, LegalPage, Section } from "@/components/legal";

export const metadata: Metadata = { title: "Privacy Policy · Saige AI" };

export default function PrivacyPage() {
  return (
    <LegalPage title="Privacy Policy">
      <p>
        Saige AI helps you run your own job search: it scores jobs against your verified profile, tailors resumes, tracks
        applications and keeps your LinkedIn and Naukri profiles sharp. This policy explains what we collect, why, and the
        control you have. The short version: your data is used only to run Saige for you, is never sold, and can be
        exported or deleted at any time.
      </p>

      <Section title="What we collect">
        <ul className="list-disc space-y-1.5 pl-5">
          <li><b>Account:</b> your name, email address and a password hash, or your Google account ID if you sign in with Google.</li>
          <li><b>Career data you provide:</b> resumes you upload, your master profile, job descriptions you add, applications, interviews, recruiter contacts you enter, and the text of your LinkedIn/Naukri profiles that you paste in.</li>
          <li><b>Gmail (only if you connect it):</b> read-only access to find job-search email such as application confirmations, interview invitations, assessments, rejections and offers.</li>
          <li><b>Usage records:</b> an audit log of actions taken in your account and technical logs (request ID, time, status) used to keep the service secure and working.</li>
        </ul>
      </Section>

      <Section title="How we use it">
        <ul className="list-disc space-y-1.5 pl-5">
          <li>To provide Saige&apos;s features for you: matching, tailoring, tracking, reminders and analytics.</li>
          <li>To check every AI-generated statement against your verified profile so nothing about you is invented.</li>
          <li>To keep your account secure (sessions, rate limits, audit logs).</li>
        </ul>
        <p>We do not sell your data, use it for advertising, or share it with recruiters or employers. Nothing is sent on your behalf: you send every application and message yourself.</p>
      </Section>

      <Section title="Google user data">
        <p>
          If you connect Gmail, Saige requests the <code>gmail.readonly</code> scope. Saige reads message metadata and content
          only to classify job-search email and update the matching application in your account. Saige never sends, deletes
          or modifies email.
        </p>
        <p>
          Saige&apos;s use and transfer of information received from Google APIs adheres to the{" "}
          <a className="underline" href="https://developers.google.com/terms/api-services-user-data-policy" target="_blank" rel="noopener noreferrer">Google API Services User Data Policy</a>,
          including the Limited Use requirements. Google user data is not used to train AI models, is not transferred to
          third parties except as needed to provide the feature you asked for, and is never used for advertising. No person
          reads your email unless you ask us to for support, or the law requires it.
        </p>
        <p>
          If you connect with a Google App Password instead, Saige uses it only to read job-search mail over Gmail&apos;s
          IMAP service, never marks mail as read, and stores it encrypted. You can revoke it in your Google account at any
          time. OAuth tokens are encrypted at rest (AES-GCM). You can disconnect Gmail at any time from Integrations, which
          revokes Saige&apos;s access immediately.
        </p>
      </Section>

      <Section title="WhatsApp alerts (optional)">
        <p>
          If you turn on WhatsApp alerts, the text of each Saige notification (for example “Email sent to Priya · PayCo”)
          is sent to your own WhatsApp number through CallMeBot, a third-party relay. Your CallMeBot key is stored
          encrypted. Turn alerts off or remove them in Integrations at any time.
        </p>
      </Section>

      <Section title="Sending email on your behalf">
        <p>
          If you connect Gmail with an App Password, Saige can send a recruiter email from your address, but only one you
          approved, and never more than 10 a day. Every sent email is listed in Recruiters.
        </p>
      </Section>

      <Section title="AI processing">
        <p>
          Some features can use Anthropic&apos;s Claude API to improve wording. When enabled, the relevant text (for example a
          job description and your verified profile facts) is sent to Anthropic for processing under its commercial terms,
          which do not allow training on this data. Saige works fully without it.
        </p>
      </Section>

      <Section title="Where data is stored">
        <p>
          Data is stored in MongoDB Atlas and processed on Vercel. Both encrypt data in transit and at rest. Sessions use a
          secure, HttpOnly cookie. Browser-extension tokens are stored only as one-way hashes.
        </p>
      </Section>

      <Section title="Your choices">
        <ul className="list-disc space-y-1.5 pl-5">
          <li><b>Export:</b> download all your data as JSON from Automation &amp; Privacy.</li>
          <li><b>Delete:</b> delete your account there. All your records, files, tokens and connections are erased.</li>
          <li><b>Pause:</b> pause any automation, or all of it, at any time.</li>
          <li><b>Disconnect:</b> revoke Gmail or browser-extension access whenever you like.</li>
        </ul>
      </Section>

      <Section title="Contact">
        <p>Questions or requests: <a className="underline" href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.</p>
      </Section>
    </LegalPage>
  );
}
