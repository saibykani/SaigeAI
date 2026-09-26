import type { Metadata } from "next";
import Link from "next/link";

import { CONTACT_EMAIL, LegalPage, Section } from "@/components/legal";

export const metadata: Metadata = { title: "Terms of Service · Saige AI" };

export default function TermsPage() {
  return (
    <LegalPage title="Terms of Service">
      <p>By creating an account or using Saige AI you agree to these terms. If you don&apos;t agree, please don&apos;t use the service.</p>

      <Section title="The service">
        <p>
          Saige AI is a personal job-search assistant. It helps you organise jobs, tailor documents, track applications and
          improve your public profiles. It does not guarantee interviews, offers or any particular result.
        </p>
      </Section>

      <Section title="Your responsibilities">
        <ul className="list-disc space-y-1.5 pl-5">
          <li>Keep the information in your profile truthful. Saige only uses facts you have verified, and you remain responsible for everything you submit to employers.</li>
          <li>Review documents, answers and messages before you use them. You send every application and message yourself.</li>
          <li>Follow the terms of the sites you use, including LinkedIn, Naukri and job boards. Saige does not log in to or automate those sites for you.</li>
          <li>Only add recruiter or referral contacts you have a legitimate reason to contact, and respect anyone who asks not to be contacted.</li>
          <li>Keep your password and extension tokens private.</li>
        </ul>
      </Section>

      <Section title="Acceptable use">
        <p>
          Don&apos;t use Saige to send spam, misrepresent yourself, scrape or overload other services, break the law, or try to
          access other users&apos; data. We may suspend accounts that do.
        </p>
      </Section>

      <Section title="Your content">
        <p>
          You own your resumes, profile and other content. You give Saige permission to process it only to provide the
          service to you, as described in the <Link className="underline" href="/privacy">Privacy Policy</Link>. You can
          export or delete it at any time.
        </p>
      </Section>

      <Section title="Availability and changes">
        <p>
          The service is provided &quot;as is&quot;, without warranties. It may change, be interrupted or be discontinued. If these
          terms change materially, we&apos;ll update the date above and let you know in the app.
        </p>
      </Section>

      <Section title="Liability">
        <p>
          To the extent the law allows, Saige AI is not liable for indirect or consequential losses, or for decisions made by
          employers or third-party platforms.
        </p>
      </Section>

      <Section title="Contact">
        <p><a className="underline" href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a></p>
      </Section>
    </LegalPage>
  );
}
