import 'package:material_ui/material_ui.dart';

import '../../core/motion.dart';
import '../../core/resource.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/forms.dart';
import '../../core/widgets/kit.dart';
import '../../core/widgets/ui.dart';
import '../search/saved_jobs_screen.dart' show RefreshIndicatorList;
import 'outreach_screen.dart';

const _roles = {'recruiter': 'Recruiter', 'hiring_manager': 'Hiring manager', 'referral': 'Referral', 'alumni': 'Alumni', 'other': 'Other'};

/// Your recruiter and referral contacts. Contacts come only from you (manual, CSV, inbox); nothing is scraped.
class RecruitersScreen extends StatefulWidget {
  const RecruitersScreen({super.key});
  @override
  State<RecruitersScreen> createState() => _RecruitersScreenState();
}

class _RecruitersScreenState extends State<RecruitersScreen> {
  final _q = TextEditingController();
  late final Resource<List<Map<String, dynamic>>> _r = Resource(() async => asList(await Session.I.api.get('/recruiters', query: {if (_q.text.trim().isNotEmpty) 'q': _q.text.trim()})));
  final _stats = Resource<Map<String, dynamic>>(() async => asMap(await Session.I.api.get('/outreach/stats')));

  @override
  void initState() {
    super.initState();
    _r.load();
    _stats.load();
  }

  @override
  void dispose() {
    _q.dispose();
    _r.dispose();
    _stats.dispose();
    super.dispose();
  }

  Future<void> _add() async {
    final done = await showSheet<bool>(context, (c) => const _AddContact());
    if (done == true) _r.load();
  }

  Future<void> _open(Map<String, dynamic> c) async {
    await showSheet<void>(context, (ctx) => _ContactSheet(contact: c, onChanged: () {
          _r.load();
          _stats.load();
        }));
  }

  @override
  Widget build(BuildContext context) => FeatureScaffold(
        title: 'Recruiters',
        subtitle: 'People you reach out to, never scraped',
        child: Stack(children: [
          Column(children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 0, 20, 8),
              child: TextField(
                controller: _q,
                textInputAction: TextInputAction.search,
                onSubmitted: (_) => _r.load(),
                decoration: InputDecoration(hintText: 'Search name, company, title', prefixIcon: Icon(Icons.search_rounded, color: C.muted), contentPadding: const EdgeInsets.symmetric(vertical: 14)),
              ),
            ),
            ListenableBuilder(
              listenable: _stats,
              builder: (context, _) {
                final s = _stats.data;
                if (s == null) return const SizedBox.shrink();
                final lim = (s['daily_limit'] as num?) ?? 10;
                final used = (s['sent_today'] as num?) ?? 0;
                return Padding(
                  padding: const EdgeInsets.fromLTRB(20, 0, 20, 10),
                  child: GlassCard(
                    radius: R.md,
                    padding: const EdgeInsets.all(14),
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Row(children: [Text('Sent today', style: T.small), const Spacer(), Text('$used / $lim', style: const TextStyle(fontWeight: FontWeight.w700))]),
                      const SizedBox(height: 8),
                      BarFill(value: lim == 0 ? 0 : used / lim, color: used >= lim ? C.bad : C.primary),
                    ]),
                  ),
                );
              },
            ),
            Expanded(
              child: ResourceView<List<Map<String, dynamic>>>(
                resource: _r,
                builder: (context, l) {
                  if (l.isEmpty) return EmptyState(icon: Icons.groups_rounded, title: 'No contacts yet', body: 'Add a recruiter or a referral you know. Saige drafts truthful messages from your verified profile.', action: 'Add contact', onAction: _add);
                  return RefreshIndicatorList(onRefresh: () async {
                    await _r.load();
                    await _stats.load();
                  }, children: [
                    for (final (i, c) in l.indexed)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 10),
                        child: Stagger(
                          index: i % 8,
                          child: GlassCard(
                            radius: R.md,
                            padding: const EdgeInsets.all(14),
                            onTap: () => _open(c),
                            child: Row(children: [
                              CircleAvatar(radius: 22, backgroundColor: C.primarySoft, child: Text(('${c['name']}'.isEmpty ? '?' : '${c['name']}'[0]).toUpperCase(), style: TextStyle(color: C.primary, fontWeight: FontWeight.w700))),
                              const SizedBox(width: 12),
                              Expanded(
                                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                  Text('${c['name']}', maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w600)),
                                  Text('${c['title'] ?? _roles[c['role']] ?? ''}  ·  ${c['company']}', maxLines: 1, overflow: TextOverflow.ellipsis, style: T.small),
                                ]),
                              ),
                              if (c['unsubscribed'] == true) Pill('Opted out', color: C.bad) else if (c['last_contacted_at'] != null) Pill('Contacted', color: C.good),
                            ]),
                          ),
                        ),
                      ),
                    const SizedBox(height: 70),
                  ]);
                },
              ),
            ),
          ]),
          Positioned(right: 20, bottom: 24, child: PillFab(label: 'Add', icon: Icons.person_add_alt_1_rounded, onTap: _add)),
        ]),
      );
}

class _AddContact extends StatefulWidget {
  const _AddContact();
  @override
  State<_AddContact> createState() => _AddContactState();
}

class _AddContactState extends State<_AddContact> {
  final _name = TextEditingController();
  final _company = TextEditingController();
  final _email = TextEditingController();
  final _title = TextEditingController();
  String _role = 'recruiter';
  bool _busy = false;

  @override
  void dispose() {
    for (final c in [_name, _company, _email, _title]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _save() async {
    if (_name.text.trim().isEmpty || _company.text.trim().isEmpty) {
      toast(context, 'Add a name and a company.', error: true);
      return;
    }
    setState(() => _busy = true);
    final r = await guarded(context, () => Session.I.api.post('/recruiters', data: {'name': _name.text.trim(), 'company': _company.text.trim(), if (_email.text.trim().isNotEmpty) 'email': _email.text.trim(), if (_title.text.trim().isNotEmpty) 'title': _title.text.trim(), 'role': _role}), ok: 'Contact added');
    if (!mounted) return;
    if (r != null) {
      success();
      Navigator.pop(context, true);
    } else {
      setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Text('New contact', style: T.h2),
        const SizedBox(height: 14),
        LabeledField(label: 'Name', controller: _name),
        const SizedBox(height: 12),
        LabeledField(label: 'Company', controller: _company),
        const SizedBox(height: 12),
        LabeledField(label: 'Email (optional)', controller: _email, keyboard: TextInputType.emailAddress),
        const SizedBox(height: 12),
        LabeledField(label: 'Title (optional)', controller: _title),
        const SizedBox(height: 14),
        ChipRow(padding: 0, options: _roles.keys.toList(), labels: _roles, value: _role, onChanged: (v) => setState(() => _role = v)),
        const SizedBox(height: 18),
        PrimaryButton(label: 'Save contact', busy: _busy, onTap: _save),
      ]);
}

const _kinds = {'referral': 'Referral ask', 'cold': 'Introduction', 'hiring_manager': 'Hiring manager', 'employee_intro': 'Employee intro', 'linkedin_note': 'LinkedIn note', 'thank_you': 'Thank you'};

class _ContactSheet extends StatefulWidget {
  const _ContactSheet({required this.contact, required this.onChanged});
  final Map<String, dynamic> contact;
  final VoidCallback onChanged;
  @override
  State<_ContactSheet> createState() => _ContactSheetState();
}

class _ContactSheetState extends State<_ContactSheet> {
  String _kind = 'referral';
  final _ctx = TextEditingController();
  bool _busy = false;

  @override
  void dispose() {
    _ctx.dispose();
    super.dispose();
  }

  Future<void> _draft() async {
    setState(() => _busy = true);
    final r = await guarded(context, () => Session.I.api.post('/outreach/draft', data: {'contact_id': widget.contact['id'], 'kind': _kind, if (_ctx.text.trim().isNotEmpty) 'context': _ctx.text.trim()}));
    if (!mounted) return;
    setState(() => _busy = false);
    if (r != null) {
      success();
      widget.onChanged();
      final o = asMap(r);
      Navigator.pop(context);
      await showSheet<void>(context, (c) => OutreachDetail(item: o, onChanged: widget.onChanged));
    }
  }

  Future<void> _delete() async {
    if (!await confirmSheet(context, title: 'Delete contact?', body: 'Drafts and history stay, but this contact is removed.', action: 'Delete', danger: true)) return;
    if (!mounted) return;
    final r = await guarded(context, () => Session.I.api.request('DELETE', '/recruiters/${widget.contact['id']}'), ok: 'Contact deleted');
    if (r != null || !mounted) {
      widget.onChanged();
      if (mounted) Navigator.pop(context);
    }
  }

  @override
  Widget build(BuildContext context) {
    final c = widget.contact;
    final unsub = c['unsubscribed'] == true;
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Text('${c['name']}', style: T.h2),
      Text('${c['title'] ?? _roles[c['role']] ?? ''}  ·  ${c['company']}', style: T.small),
      if (c['email'] != null) ...[const SizedBox(height: 6), Text('${c['email']}', style: T.small)],
      const SizedBox(height: 16),
      if (unsub)
        Text('This contact opted out. Saige will not draft messages to them.', style: TextStyle(color: C.bad))
      else ...[
        Text('DRAFT A MESSAGE', style: T.label),
        const SizedBox(height: 8),
        ChipRow(padding: 0, options: _kinds.keys.toList(), labels: _kinds, value: _kind, onChanged: (v) => setState(() => _kind = v)),
        const SizedBox(height: 12),
        LabeledField(label: 'Context (optional)', controller: _ctx, hint: 'We worked together at ...', lines: 2),
        const SizedBox(height: 6),
        Text('Drafts only use facts from your verified profile and are checked by the truth guard. Nothing is sent until you approve.', style: T.small),
        const SizedBox(height: 14),
        PrimaryButton(label: 'Draft message', icon: Icons.edit_note_rounded, busy: _busy, onTap: _draft),
      ],
      const SizedBox(height: 8),
      PrimaryButton(label: 'Delete contact', ghost: true, onTap: _delete),
    ]);
  }
}
