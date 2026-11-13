import 'package:material_ui/material_ui.dart';

import '../../core/motion.dart';
import '../../core/resource.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/forms.dart';
import '../../core/widgets/kit.dart';
import '../../core/widgets/ui.dart';
import '../search/saved_jobs_screen.dart' show RefreshIndicatorList;

/// Job-seeker side of hiring: opt in to be found by recruiters and answer their interest requests.
/// Nothing about you is shared with a recruiter until you accept.
class TalentScreen extends StatefulWidget {
  const TalentScreen({super.key});
  @override
  State<TalentScreen> createState() => _TalentScreenState();
}

class _TalentScreenState extends State<TalentScreen> {
  final _set = Resource<Map<String, dynamic>>(() async => asMap(await Session.I.api.get('/talent/settings')));
  final _reqs = Resource<List<Map<String, dynamic>>>(() async => asList(await Session.I.api.get('/talent/requests')));

  @override
  void initState() {
    super.initState();
    _set.load();
    _reqs.load();
  }

  @override
  void dispose() {
    _set.dispose();
    _reqs.dispose();
    super.dispose();
  }

  Future<void> _toggle(bool v) async {
    final r = await guarded(context, () => Session.I.api.put('/talent/settings', data: {'discoverable': v}), ok: v ? 'Recruiters can find you' : 'You are hidden from recruiters');
    if (r != null) {
      _set.set(asMap(r));
      Session.I.user['discoverable'] = v;
    }
  }

  Future<void> _respond(Map<String, dynamic> r, bool accept) async {
    final ok = await guarded(context, () => Session.I.api.post('/talent/requests/${r['id']}/respond', data: {'accept': accept}), ok: accept ? 'Accepted. Your contact details were shared.' : 'Declined');
    if (ok != null) {
      success();
      _reqs.load();
    }
  }

  @override
  Widget build(BuildContext context) => FeatureScaffold(
        title: 'Recruiters',
        subtitle: 'You decide who can reach you',
        child: ListenableBuilder(
          listenable: Listenable.merge([_set, _reqs]),
          builder: (context, _) {
            if (_set.data == null || _reqs.data == null) {
              final e = _set.error ?? _reqs.error;
              return e != null ? ErrorState(error: e, onRetry: () { _set.load(); _reqs.load(); }) : const LoadingState();
            }
            final on = _set.data!['discoverable'] == true;
            final l = _reqs.data!;
            return RefreshIndicatorList(onRefresh: () => Future.wait([_set.load(), _reqs.load()]), children: [
              Stagger(
                index: 0,
                child: GlassCard(
                  padding: EdgeInsets.zero,
                  child: ToggleRow(icon: Icons.visibility_rounded, title: 'Let recruiters find me', sub: 'Shows your name, role and verified skills. Contact details stay private until you accept.', value: on, onChanged: _toggle),
                ),
              ),
              const SectionTitle('Requests'),
              if (l.isEmpty)
                const EmptyState(icon: Icons.mark_email_unread_rounded, title: 'No requests yet', body: 'When a recruiter is interested, you will see it here and in Notifications.')
              else
                for (final (i, r) in l.indexed)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: Stagger(
                      index: i % 8 + 1,
                      child: GlassCard(
                        radius: R.md,
                        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          Row(children: [Expanded(child: Text('${r['recruiter_name']}', style: const TextStyle(fontWeight: FontWeight.w700))), Pill(prettyStatus('${r['status']}'), color: r['status'] == 'accepted' ? C.good : (r['status'] == 'declined' ? C.muted : C.warn), filled: true)]),
                          if (r['job_title'] != null) Text('${r['job_title']}${r['company'] != null ? ' at ${r['company']}' : ''}', style: T.small),
                          if ('${r['message']}'.isNotEmpty) ...[const SizedBox(height: 8), Text('${r['message']}', style: T.body.copyWith(fontSize: 14))],
                          if (r['status'] == 'pending') ...[
                            const SizedBox(height: 12),
                            Row(children: [
                              Expanded(child: PrimaryButton(label: 'Accept', onTap: () => _respond(r, true))),
                              const SizedBox(width: 8),
                              Expanded(child: PrimaryButton(label: 'Decline', ghost: true, onTap: () => _respond(r, false))),
                            ]),
                          ],
                        ]),
                      ),
                    ),
                  ),
            ]);
          },
        ),
      );
}
