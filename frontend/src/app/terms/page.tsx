import Link from "next/link";

export const metadata = {
  title: "Terms of Service | Gmail Reminder",
  description: "Terms governing use of Gmail Reminder.",
};

const sections = [
  ["1. About the service", "Gmail Reminder helps users connect a Google account, identify email content that may need attention, and create reminders or notifications. Features may change as the service develops."],
  ["2. Eligibility and accounts", "You must be legally able to enter into these terms. Keep your sign-in credentials secure, provide accurate account information, and notify the service if you suspect unauthorized access. You are responsible for activity carried out through your account."],
  ["3. Google and Gmail access", "Connecting Gmail is optional and requires a separate Google authorization. You choose whether to grant the requested permissions. Gmail access is used to provide the features you enable, such as email processing, reminders and synchronization. You can revoke access through your Google Account security settings and disconnect a mailbox in the application where available."],
  ["4. Acceptable use", "Do not misuse the service, interfere with its operation, attempt unauthorized access, upload malicious content, or use it in a way that violates applicable law or another person's rights."],
  ["5. Notifications and third-party services", "If you configure Telegram, WhatsApp or another supported destination, you authorize the service to send the notifications you configure to that destination. Third-party platforms have their own terms, privacy practices, availability and delivery limitations."],
  ["6. Accuracy and availability", "Email classification, extracted dates and automated reminders may be incomplete or incorrect. The service is an assistance tool, not a substitute for checking important messages, deadlines or commitments yourself. We do not guarantee uninterrupted availability or delivery of every notification."],
  ["7. Your content and permissions", "You retain rights to your email and other content. You grant the limited permissions needed to process that content to provide the service you request. Do not connect accounts or destinations that you are not authorized to use."],
  ["8. Suspension and termination", "You may stop using the service and disconnect integrations. We may suspend or restrict access where reasonably necessary to protect the service, users, third parties or comply with law."],
  ["9. Changes", "We may update these terms as the service changes. The current version and its effective date will be shown on this page. Material changes may be communicated through the service where appropriate."],
  ["10. Contact", "For questions about these terms, use the support or contact channel published within the application."],
];

export default function TermsPage() {
  return <main className="min-h-screen bg-background px-4 py-12 text-foreground"><article className="mx-auto max-w-3xl space-y-8"><header className="space-y-3"><Link href="/signup" className="text-sm text-primary hover:underline">← Back to sign up</Link><p className="text-sm font-semibold uppercase tracking-wider text-primary">Gmail Reminder</p><h1 className="text-3xl font-bold tracking-tight">Terms of Service</h1><p className="text-sm text-muted-foreground">Effective date: 31 October 2026</p><p className="text-muted-foreground">Please read these terms before using Gmail Reminder.</p></header>{sections.map(([heading, body]) => <section key={heading} className="space-y-2"><h2 className="text-lg font-semibold">{heading}</h2><p className="leading-7 text-muted-foreground">{body}</p></section>)}<footer className="border-t border-border pt-6 text-sm text-muted-foreground"><Link href="/privacy" className="text-primary hover:underline">Read the Privacy Policy</Link></footer></article></main>;
}
