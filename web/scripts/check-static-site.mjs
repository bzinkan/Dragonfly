import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const read = (path) => readFileSync(join(root, path), "utf8");

const pages = {
  "public/index.html": read("public/index.html"),
  "public/privacy.html": read("public/privacy.html"),
  "public/terms.html": read("public/terms.html"),
  "public/support.html": read("public/support.html"),
  "public/contact.html": read("public/contact.html"),
};
const staticWebAppConfig = JSON.parse(read("public/staticwebapp.config.json"));

const failures = [];
const pilotMailtoSubject = "mailto:support@dragonfly-app.net?subject=Dragonfly%20pilot%20access%20request";
const pilotMailtoFields = [
  "Parent%2Fguardian%20name%3A",
  "Email%3A",
  "Number%20of%20kids%3A",
  "Kids%27%20age%20range%3A",
  "Android%20phone%20available%3F%3A",
  "Are%20you%20willing%20to%20test%20with%20your%20child%20present%3F%3A",
  "Anything%20we%20should%20know%3F%3A",
];

function expectIncludes(file, text) {
  if (!pages[file].includes(text)) {
    failures.push(`${file} is missing: ${text}`);
  }
}

function expectAbsent(file, pattern, label) {
  if (pattern.test(pages[file])) {
    failures.push(`${file} contains disallowed copy: ${label}`);
  }
}

expectIncludes("public/index.html", "Turn backyard curiosity into real science.");
expectIncludes("public/index.html", "curious explorers of all ages");
expectIncludes("public/index.html", "Request pilot access");
expectIncludes("public/index.html", pilotMailtoSubject);
expectIncludes("public/index.html", "Parent%2Fguardian%20name%3A%0D%0AEmail%3A");
expectIncludes("public/index.html", "Please do not include your child&rsquo;s full name in this request.");
expectIncludes("public/index.html", "Dragonfly is in a small supervised pilot. We&rsquo;ll reply if we can include your family in the next test group.");
expectIncludes("public/index.html", "What happens next?");
expectIncludes("public/index.html", "We review pilot requests.");
expectIncludes("public/index.html", "If selected, we send Android internal-testing instructions.");
expectIncludes("public/index.html", "A parent or guardian helps create the kid account.");
expectIncludes("public/index.html", "The first test should happen with the adult present.");
expectIncludes("public/index.html", 'id="how-it-works"');
expectIncludes("public/index.html", 'id="sanctuary"');
expectIncludes("public/index.html", 'id="safety"');
expectIncludes("public/index.html", 'id="pilot"');
expectIncludes("public/index.html", 'id="faq"');
expectIncludes("public/index.html", "support@dragonfly-app.net");
expectIncludes("public/index.html", "privacy@dragonfly-app.net");
expectIncludes("public/index.html", 'href="/privacy"');
expectIncludes("public/index.html", 'href="/terms"');
expectIncludes("public/index.html", 'href="/support"');
expectIncludes("public/index.html", 'href="/contact"');

expectIncludes("public/privacy.html", "This page is written for the Dragonfly pilot and will be updated before broader release.");
expectIncludes("public/privacy.html", "curious explorers of all ages");
expectIncludes("public/privacy.html", "Organism photos");
expectIncludes("public/privacy.html", "Observation location");
expectIncludes("public/privacy.html", "Species selection");
expectIncludes("public/privacy.html", "Kid display name or nickname");
expectIncludes("public/privacy.html", "No ads.");
expectIncludes("public/privacy.html", "No selling or renting personal data.");
expectIncludes("public/privacy.html", "iNaturalist public submission is pilot-limited");
expectIncludes("public/privacy.html", "privacy@dragonfly-app.net");
expectIncludes("public/privacy.html", "Last updated: June 10, 2026.");

expectIncludes("public/terms.html", "Dragonfly is a beta/pilot product");
expectIncludes("public/terms.html", "Kids should use Dragonfly only with adult permission");
expectIncludes("public/terms.html", "No emergency or safety use");
expectIncludes("public/terms.html", "Do not upload harmful, inappropriate");
expectIncludes("public/terms.html", "No public social network features");
expectIncludes("public/terms.html", "support@dragonfly-app.net");

expectIncludes("public/support.html", "support@dragonfly-app.net");
expectIncludes("public/support.html", "Device model");
expectIncludes("public/support.html", "Android version");
expectIncludes("public/support.html", "Wrong account data visible");
expectIncludes("public/support.html", "A photo or privacy concern");
expectIncludes("public/support.html", 'href="/privacy"');
expectIncludes("public/support.html", 'href="/contact"');

expectIncludes("public/contact.html", "support@dragonfly-app.net");
expectIncludes("public/contact.html", "privacy@dragonfly-app.net");
expectIncludes("public/contact.html", "Request pilot access");
expectIncludes("public/contact.html", pilotMailtoSubject);
expectIncludes("public/contact.html", "Parent%2Fguardian%20name%3A%0D%0AEmail%3A");
expectIncludes("public/contact.html", "Please do not include your child&rsquo;s full name in this request.");
expectIncludes("public/contact.html", "Dragonfly is in a small supervised pilot. We&rsquo;ll reply if we can");
expectIncludes("public/contact.html", "Dragonfly is in limited Android testing");

for (const file of ["public/index.html", "public/contact.html"]) {
  for (const field of pilotMailtoFields) {
    expectIncludes(file, field);
  }
}

const rewrites = new Map(
  staticWebAppConfig.routes.map((route) => [route.route, route.rewrite]),
);

for (const [route, rewrite] of [
  ["/privacy", "/privacy.html"],
  ["/terms", "/terms.html"],
  ["/support", "/support.html"],
  ["/contact", "/contact.html"],
]) {
  if (rewrites.get(route) !== rewrite) {
    failures.push(`public/staticwebapp.config.json must rewrite ${route} to ${rewrite}`);
  }
}

const forbiddenCopy = [
  [/COPPA compliant/i, "COPPA compliant"],
  [/Google Play Families approved/i, "Google Play Families approved"],
  [/fully moderated in real time/i, "fully moderated in real time"],
  [/submitted automatically to iNaturalist/i, "submitted automatically to iNaturalist"],
  [/automatic iNaturalist submission/i, "automatic iNaturalist submission"],
  [/no location collected/i, "no location collected"],
  [/kids ages 9(?:-|&ndash;|–)12/i, "kids ages 9-12"],
  [/field app for kids ages/i, "field app for kids ages"],
  [/Dragonfly%20Android%20pilot/i, "old Android pilot mailto subject"],
  [/Kid%20age%20range/i, "old kid age mailto field"],
  [/Adult%20name%3A/i, "old adult name mailto field"],
  [/child(?:%27|'|&rsquo;)s%20full%20name%3A/i, "child full name mailto field"],
  [/school%20name%3A/i, "school name mailto field"],
];

for (const file of Object.keys(pages)) {
  for (const [pattern, label] of forbiddenCopy) {
    expectAbsent(file, pattern, label);
  }
}

for (const [file, content] of Object.entries(pages)) {
  if (/<script[\s>]/i.test(content)) {
    failures.push(`${file} must work without JavaScript`);
  }

  if (/<(?:script|iframe|img)[^>]+(?:analytics|googletagmanager|gtag|facebook\.net|doubleclick|pixel)/i.test(content)) {
    failures.push(`${file} appears to include analytics or tracking code`);
  }
}

if (failures.length > 0) {
  console.error(failures.join("\n"));
  process.exit(1);
}

console.log("Static landing checks passed.");
