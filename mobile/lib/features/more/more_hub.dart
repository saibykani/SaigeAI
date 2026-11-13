import 'package:material_ui/material_ui.dart';

import '../../core/motion.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/kit.dart';
import '../growth/company_insights_screen.dart';
import '../growth/growth_screen.dart';
import '../growth/learning_screen.dart';
import '../inbox/inbox_screen.dart';
import '../interviews/interviews_screen.dart';
import '../mock/mock_setup_screen.dart';
import '../network/linkedin_posts_screen.dart';
import '../network/outreach_screen.dart';
import '../network/recruiters_screen.dart';
import '../notifications/notifications_screen.dart';
import '../portfolio/portfolio_screen.dart';
import '../profile/profile_optimiser_screen.dart';
import '../roles/admin_screen.dart';
import '../roles/hiring_screen.dart';
import '../roles/talent_screen.dart';
import '../settings/integrations_screen.dart';
import '../settings/settings_screen.dart';
import '../resume/ats_coach_screen.dart';
import '../resume/cover_letter_screen.dart';
import '../resume/health_screen.dart';
import '../search/careers_screen.dart';
import '../search/find_jobs_screen.dart';
import '../search/saved_jobs_screen.dart';

class _Item {
  const _Item(this.id, this.title, this.sub, this.icon, this.color, this.build);
  final String id;
  final String title;
  final String sub;
  final IconData icon;
  final Color color;
  final Widget Function() build;
}

class _Group {
  const _Group(this.title, this.items);
  final String title;
  final List<_Item> items;
}


List<_Group> get _groups => <_Group>[
  if (Session.I.isRecruiter || Session.I.isAdmin)
    _Group(Session.I.isAdmin ? 'Admin' : 'Hiring', [
      if (Session.I.isRecruiter) _Item('hiring', 'Hiring', 'Jobs, candidates, requests', Icons.groups_rounded, C.violet, () => const HiringScreen()),
      if (Session.I.isAdmin) _Item('admin', 'Admin console', 'KPIs and users', Icons.admin_panel_settings_rounded, C.bad, () => const AdminScreen()),
    ]),
  _Group('Resume & ATS', [
    _Item('ats', 'ATS coach', 'Score for any role, then build', Icons.bolt_rounded, C.blue, () => const AtsCoachScreen()),
    _Item('health', 'Resume health', 'Line by line, your numbers', Icons.monitor_heart_rounded, C.good, () => const ResumeHealthScreen()),
    _Item('cover', 'Cover letter', 'Truth-checked, per job', Icons.edit_note_rounded, C.violet, () => const CoverLetterScreen()),
  ]),
  _Group('Job search', [
    _Item('find', 'Find jobs', 'Live job APIs, scored', Icons.travel_explore_rounded, C.teal, () => const FindJobsScreen()),
    _Item('careers', 'Career portals', '65+ company pages', Icons.business_center_rounded, C.warn, () => const CareersScreen()),
    _Item('saved', 'Saved jobs', 'Filter everything tracked', Icons.bookmarks_rounded, C.lime, () => const SavedJobsScreen()),
  ]),
  _Group('Network', [
    _Item('recruiters', 'Recruiters', 'Contacts and truthful drafts', Icons.groups_rounded, C.violet, () => const RecruitersScreen()),
    _Item('outreach', 'Outreach', 'Approve and send, 10 a day', Icons.send_rounded, C.blue, () => const OutreachScreen()),
    _Item('ofollow', 'Outreach follow-ups', 'Due after no reply', Icons.reply_all_rounded, C.warn, () => const OutreachScreen(initial: 'followups')),
    _Item('referrals', 'Referrals', 'Per job, who you asked', Icons.handshake_rounded, C.good, () => const ReferralsScreen()),
    _Item('lposts', 'LinkedIn posts', 'Daily posts, your skills', Icons.campaign_rounded, C.blue, () => const LinkedInPostsScreen()),
    _Item('inbox', 'Inbox', 'Interviews, offers, replies', Icons.mark_email_unread_rounded, C.bad, () => const InboxScreen()),
    _Item('interviews', 'Interviews', 'Upcoming and from mail', Icons.event_available_rounded, C.teal, () => const InterviewsScreen()),
  ]),
  _Group('Growth', [
    _Item('goals', 'Weekly goals', 'Targets and progress', Icons.flag_rounded, C.good, () => const GrowthScreen()),
    _Item('follow', 'Follow-ups', 'Silent for 10+ days', Icons.mark_chat_unread_rounded, C.warn, () => const GrowthScreen(initial: 'followups')),
    _Item('salary', 'Salary insight', 'From real postings', Icons.payments_rounded, C.lime, () => const GrowthScreen(initial: 'salary')),
    _Item('learn', 'Learning path', 'Close skill gaps', Icons.school_rounded, C.violet, () => const LearningScreen()),
    _Item('insights', 'Company insights', 'Your reply rates', Icons.insights_rounded, C.teal, () => const CompanyInsightsScreen()),
    _Item('mock', 'Mock interview', 'Voice interviewer', Icons.record_voice_over_rounded, C.violet, () => const MockSetupScreen()),
  ]),
  _Group('Profile & presence', [
    _Item('optim', 'Profile optimiser', 'LinkedIn and Naukri edits', Icons.auto_fix_high_rounded, C.teal, () => const ProfileOptimiserScreen()),
    _Item('portfolio', 'Portfolio', 'Publish a page of you', Icons.web_rounded, C.violet, () => const PortfolioScreen()),
    if (!Session.I.isRecruiter) _Item('talent', 'Recruiters find me', 'Opt in, answer requests', Icons.visibility_rounded, C.lime, () => const TalentScreen()),
  ]),
  _Group('Account', [
    _Item('notes', 'Notifications', 'Everything Saige did', Icons.notifications_active_rounded, C.warn, () => const NotificationsScreen()),
    _Item('integrations', 'Integrations', 'Gmail, WhatsApp, Telegram', Icons.hub_rounded, C.teal, () => const IntegrationsScreen()),
    _Item('settings', 'Settings', 'Theme, automation, privacy', Icons.settings_rounded, C.primary, () => const SettingsScreen()),
  ]),
];

/// Launcher for every Saige feature: grouped, animated tiles; the tapped icon flies into the next screen's header.
class MoreHub extends StatelessWidget {
  const MoreHub({super.key});

  @override
  Widget build(BuildContext context) {
    var n = 0;
    return FeatureScaffold(
      title: 'Everything',
      subtitle: 'All of Saige in one place',
      child: ListView(
        physics: const BouncingScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(20, 4, 20, 120),
        children: [
          for (final g in _groups) ...[
            Stagger(index: n++ ~/ 2, child: Padding(padding: const EdgeInsets.fromLTRB(4, 20, 4, 12), child: Text(g.title.toUpperCase(), style: T.label))),
            GridView.count(
              crossAxisCount: 2,
              mainAxisSpacing: 12,
              crossAxisSpacing: 12,
              childAspectRatio: 1.18,
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              children: [for (final it in g.items) Stagger(index: n++ ~/ 2, child: _Tile(it))],
            ),
          ],
          const SizedBox(height: 24),
          Center(child: Text('Saige never invents facts and never sends anything without your approval.', style: T.small, textAlign: TextAlign.center)),
        ],
      ),
    );
  }
}

class _Tile extends StatelessWidget {
  const _Tile(this.it);
  final _Item it;

  @override
  Widget build(BuildContext context) => Pressable(
        scale: 0.94,
        onTap: () => pushDepth(context, (_) => HeroScope(tag: 'more-${it.id}', icon: it.icon, color: it.color, child: it.build())),
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(R.lg),
            color: Color.alphaBlend(it.color.withValues(alpha: C.dark ? 0.12 : 0.1), C.surface),
            boxShadow: C.shadow,
          ),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
            Hero(
              tag: 'more-${it.id}',
              child: Container(width: 44, height: 44, decoration: BoxDecoration(shape: BoxShape.circle, color: it.color.withValues(alpha: 0.2)), child: Icon(it.icon, color: it.color, size: 22)),
            ),
            Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(it.title, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15.5, letterSpacing: -0.2)),
              const SizedBox(height: 2),
              Text(it.sub, maxLines: 2, overflow: TextOverflow.ellipsis, style: T.small.copyWith(fontSize: 12)),
            ]),
          ]),
        ),
      );
}
