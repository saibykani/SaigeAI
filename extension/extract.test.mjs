import test from "node:test";
import assert from "node:assert/strict";
import X from "./extract.js";

const FEED_POSTS = [
  { top: -400, bottom: -50, text: "We're hiring! Java Developer at Old Corp. Send your CV to old@corp.com. 3+ years experience with Java." },
  { top: 100, bottom: 300, text: "Congratulations to our newest graduates at Yale School of Management! Proud of every one of you, great work team." },
  { top: 320, bottom: 700, text: "We're hiring! SDET at Acme Labs, Bengaluru. 3-5 years with Selenium and Java. Send your CV to careers@acmelabs.com" },
  { top: 720, bottom: 1000, text: "Excited to share that I completed my 5 year journey in product management. Thanks to everyone who helped me." },
];
const HIRING_POST = `Acme Labs
We're hiring! SDET at Acme Labs, Bengaluru.
3-5 years with Selenium, Java and API testing. Immediate joiners preferred.
Send your CV to careers@acmelabs.com with subject: SDET Application`;
const NAUKRI = `Job description
Role: Performance Test Engineer
Company: Zenith Systems
Location: Pune
Experience: 3-6 years
Key skills: JMeter, LoadRunner, Java`;

test("cleanTitle strips LinkedIn counters and suffixes", () => {
  assert.equal(X.cleanTitle("(23) Feed | LinkedIn"), "Feed");
  assert.equal(X.cleanTitle("(3) Senior SDET - LinkedIn"), "Senior SDET");
  assert.equal(X.cleanTitle("QA Engineer | Naukri.com"), "QA Engineer");
});

test("page titles like Feed are never a role", () => {
  assert.equal(X.titleCandidate("(23) Feed | LinkedIn", "Search results"), "");
  assert.equal(X.titleCandidate("(2) Senior QA Automation Engineer | LinkedIn"), "Senior QA Automation Engineer");
});

test("feed pages are feed-like, job views are not", () => {
  assert.equal(X.isFeedLike("www.linkedin.com", "/feed/"), true);
  assert.equal(X.isFeedLike("www.linkedin.com", "/in/someone/"), true);
  assert.equal(X.isFeedLike("www.linkedin.com", "/jobs/view/123/"), false);
  assert.equal(X.isFeedLike("www.naukri.com", "/job-listings-sdet"), false);
  assert.equal(X.isLinkedInJobView("www.linkedin.com", "/jobs/search/", "?currentJobId=4001"), true);
});

test("pickPost chooses the hiring post nearest the viewport centre, never a non-hiring one", () => {
  assert.equal(X.pickPost(FEED_POSTS, 800), 2);
  assert.equal(X.pickPost([FEED_POSTS[1], FEED_POSTS[3]], 800), -1);
  assert.equal(X.pickPost([FEED_POSTS[0]], 800), -1); // scrolled out of view
});

test("hiring post parsing", () => {
  const r = X.parseHiringPost(HIRING_POST);
  assert.equal(r.role, "SDET");
  assert.equal(r.company, "Acme Labs");
  assert.deepEqual(r.emails, ["careers@acmelabs.com"]);
  assert.match(r.location, /Bengaluru/);
  assert.match(r.experience, /3-5/);
  assert.equal(r.is_job, true);
});

test("opening-at pattern", () => {
  const r = X.parseHiringPost("Exciting news! Data Engineer opening at Nimbus Cloud in Pune. Apply: jobs@nimbus.io. 2+ years of experience.");
  assert.equal(r.role, "Data Engineer");
  assert.equal(r.company, "Nimbus Cloud");
});

test("naukri style labelled fields and hints", () => {
  const r = X.parseHiringPost(NAUKRI);
  assert.equal(r.role, "Performance Test Engineer");
  assert.equal(r.company, "Zenith Systems");
  assert.equal(r.location, "Pune");
  const h = X.parseHiringPost("Responsibilities\nOwn automation.", { title: "(4) Staff SDET | LinkedIn", company: "PayCo" });
  assert.equal(h.role, "Staff SDET");
  assert.equal(h.company, "PayCo");
});

test("a feed dump is not a hiring post", () => {
  const text = FEED_POSTS.filter((p, i) => i === 1 || i === 3).map((p) => p.text).join("\n");
  assert.equal(X.looksLikeHiring(text), false);
  assert.equal(X.parseHiringPost(text, { title: "(23) Feed" }).role, "");
});

test("truncation and capping", () => {
  assert.equal(X.isTruncated("We're hiring a QA lead for our team in… see more"), true);
  assert.equal(X.isTruncated("Complete text."), false);
  assert.equal(X.isTruncated("Complete text.", true), true);
  assert.equal(X.capText("a".repeat(20000)).length, 8000);
});

test("mergePostText adds image text and alt text once", () => {
  const out = X.mergePostText({ text: "Hiring now", alts: ["Role: SDET at Acme", "Image", "Role: SDET at Acme"], imageTexts: ["Requirements: Selenium, Java"] });
  assert.match(out, /Requirements: Selenium/);
  assert.equal(out.split("Role: SDET at Acme").length, 2);
  assert.doesNotMatch(out, /\nImage/);
});

test("JSON-LD JobPosting", () => {
  const r = X.fromJsonLd({ "@graph": [{ "@type": "WebPage" }, { "@type": "JobPosting", title: "QA Engineer | Naukri.com", description: "<p>Test things</p>", hiringOrganization: { name: "Globex" }, jobLocation: { address: { addressLocality: "Pune", addressCountry: "IN" } } }] });
  assert.equal(r.title, "QA Engineer");
  assert.equal(r.company, "Globex");
  assert.equal(r.location, "Pune, IN");
  assert.equal(X.fromJsonLd({ "@type": "Article" }), null);
});
