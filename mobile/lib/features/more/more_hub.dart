import 'package:material_ui/material_ui.dart';

import '../../core/motion.dart';
import '../../core/theme.dart';
import '../../core/widgets/kit.dart';
import '../growth/company_insights_screen.dart';
import '../growth/growth_screen.dart';
import '../growth/learning_screen.dart';
import '../inbox/inbox_screen.dart';
import '../interviews/interviews_screen.dart';
import '../mock/mock_setup_screen.dart';
import '../notifications/notifications_screen.dart';
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

const _teal = Color(0xFF3DDCC8);
const _violet = Color(0xFFA78BFA);
const _lime = Color(0xFFB6E84A);

final _groups = <_Group>[
  _Group('Resume & ATS', [
    _Item('ats', 'ATS coach', 'Score for any role, then build', Icons.bolt_rounded, C.primary, () => const AtsCoachScreen()),
    _Item('health', 'Resume health', 'Line by line, your numbers', Icons.monitor_heart_rounded, C.good, () => const ResumeHealthScreen()),
    _Item('cover', 'Cover letter', 'Truth-checked, per job', Icons.edit_note_rounded, _violet, () => const CoverLetterScreen()),
  ]),
  _Group('Job search', [
    _Item('find', 'Find jobs', 'Live job APIs, scored', Icons.travel_explore_rounded, _teal, () => const FindJobsScreen()),
    _Item('careers', 'Career portals', '65+ company pages', Icons.business_center_rounded, C.warn, () => const CareersScreen()),
    _Item('saved', 'Saved jobs', 'Filter everything tracked', Icons.bookmarks_rounded, _lime, () => const SavedJobsScreen()),
  ]),
  _Group('Network', [
    _Item('inbox', 'Inbox', 'Interviews, offers, replies', Icons.mark_email_unread_rounded, C.primary, () => const InboxScreen()),
    _Item('interviews', 'Interviews', 'Upcoming and from mail', Icons.event_available_rounded, _teal, () => const InterviewsScreen()),
  ]),
  _Group('Growth', [
    _Item('goals', 'Weekly goals', 'Targets and progress', Icons.flag_rounded, C.good, () => const GrowthScreen()),
    _Item('follow', 'Follow-ups', 'Silent for 10+ days', Icons.mark_chat_unread_rounded, C.warn, () => const GrowthScreen(initial: 'followups')),
    _Item('salary', 'Salary insight', 'From real postings', Icons.payments_rounded, _lime, () => const GrowthScreen(initial: 'salary')),
    _Item('learn', 'Learning path', 'Close skill gaps', Icons.school_rounded, _violet, () => const LearningScreen()),
    _Item('insights', 'Company insights', 'Your reply rates', Icons.insights_rounded, _teal, () => const CompanyInsightsScreen()),
    _Item('mock', 'Mock interview', 'Voice interviewer', Icons.record_voice_over_rounded, C.primary, () => const MockSetupScreen()),
  ]),
  _Group('Account', [
    _Item('notes', 'Notifications', 'Everything Saige did', Icons.notifications_active_rounded, C.warn, () => const NotificationsScreen()),
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
          const Center(child: Text('Saige never invents facts and never sends anything without your approval.', style: T.small, textAlign: TextAlign.center)),
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
            border: Border.all(color: C.line),
            gradient: const LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Color(0xFF131316), Color(0xFF0A0A0C)]),
          ),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
            Hero(
              tag: 'more-${it.id}',
              child: Container(width: 44, height: 44, decoration: BoxDecoration(shape: BoxShape.circle, color: it.color.withValues(alpha: 0.16), border: Border.all(color: it.color.withValues(alpha: 0.5))), child: Icon(it.icon, color: it.color, size: 22)),
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
