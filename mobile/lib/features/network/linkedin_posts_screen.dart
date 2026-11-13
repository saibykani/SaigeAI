import 'package:material_ui/material_ui.dart';

import '../../core/motion.dart';
import '../../core/resource.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/forms.dart';
import '../../core/widgets/kit.dart';
import '../../core/widgets/ui.dart';
import '../search/saved_jobs_screen.dart' show RefreshIndicatorList;

/// Daily LinkedIn posts built from your verified skills. Publishing is your approval; connecting LinkedIn
/// needs the web OAuth page, so that button opens the browser.
class LinkedInPostsScreen extends StatefulWidget {
  const LinkedInPostsScreen({super.key});
  @override
  State<LinkedInPostsScreen> createState() => _LinkedInPostsScreenState();
}

class _LinkedInPostsScreenState extends State<LinkedInPostsScreen> {
  final _status = Resource<Map<String, dynamic>>(() async => asMap(await Session.I.api.get('/linkedin/status')));
  final _posts = Resource<List<Map<String, dynamic>>>(() async => asList(await Session.I.api.get('/linkedin/posts')));
  bool _gen = false;

  @override
  void initState() {
    super.initState();
    _status.load();
    _posts.load();
  }

  @override
  void dispose() {
    _status.dispose();
    _posts.dispose();
    super.dispose();
  }

  Future<void> _refresh() => Future.wait([_status.load(), _posts.load()]);

  Future<void> _generate() async {
    setState(() => _gen = true);
    final r = await guarded(context, () => Session.I.api.post('/linkedin/posts/generate'), ok: 'Post drafted from your verified skills');
    if (!mounted) return;
    setState(() => _gen = false);
    if (r != null) {
      success();
      await _refresh();
    }
  }

  @override
  Widget build(BuildContext context) => FeatureScaffold(
        title: 'LinkedIn posts',
        subtitle: 'Truthful posts from your own skills',
        child: ListenableBuilder(
          listenable: Listenable.merge([_status, _posts]),
          builder: (context, _) {
            if (_posts.data == null || _status.data == null) {
              final e = _posts.error ?? _status.error;
              return e != null ? ErrorState(error: e, onRetry: _refresh) : const LoadingState();
            }
            final st = _status.data!;
            final connected = st['connected'] == true;
            final l = _posts.data!;
            return RefreshIndicatorList(onRefresh: _refresh, children: [
              Stagger(
                index: 0,
                child: GlassCard(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Row(children: [
                      IconBadge(connected ? Icons.link_rounded : Icons.link_off_rounded, connected ? C.good : C.warn),
                      const SizedBox(width: 12),
                      Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(connected ? 'Connected as ${st['name'] ?? 'you'}' : 'LinkedIn not connected', style: const TextStyle(fontWeight: FontWeight.w700)), Text('${st['published'] ?? 0} published  ·  streak ${st['streak'] ?? 0}', style: T.small)])),
                    ]),
                    const SizedBox(height: 14),
                    if (!connected) ...[
                      Text(st['app_configured'] == true ? 'Connecting uses LinkedIn sign-in in the browser. Until then, copy a post and publish it yourself.' : 'Publishing is not set up on the server yet. Copy a post and share it yourself.', style: T.small),
                      const SizedBox(height: 10),
                      if (st['app_configured'] == true) PrimaryButton(label: 'Connect on the web', ghost: true, icon: Icons.open_in_new_rounded, onTap: () => openUrl(context, webUrl('/linkedin'))),
                      const SizedBox(height: 8),
                    ],
                    PrimaryButton(label: 'Generate today\'s post', icon: Icons.auto_awesome_rounded, busy: _gen, onTap: _generate),
                  ]),
                ),
              ),
              const SizedBox(height: 14),
              if (l.isEmpty)
                const Padding(padding: EdgeInsets.only(top: 30), child: EmptyState(icon: Icons.article_rounded, title: 'No posts yet', body: 'Generate a post. Every claim is checked against your verified profile.'))
              else
                for (final (i, p) in l.indexed)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: Stagger(index: i % 8 + 1, child: _PostCard(post: p, connected: connected, onChanged: _refresh)),
                  ),
            ]);
          },
        ),
      );
}

class _PostCard extends StatelessWidget {
  const _PostCard({required this.post, required this.connected, required this.onChanged});
  final Map<String, dynamic> post;
  final bool connected;
  final VoidCallback onChanged;

  Future<void> _publish(BuildContext context) async {
    final ok = await confirmSheet(context, title: 'Publish to LinkedIn?', body: 'This posts the text below on your LinkedIn profile now.', action: 'Approve and publish');
    if (!ok || !context.mounted) return;
    final r = await guarded(context, () => Session.I.api.post('/linkedin/posts/${post['id']}/publish'), ok: 'Published');
    if (r != null) {
      success();
      onChanged();
    }
  }

  Future<void> _edit(BuildContext context) async {
    final c = TextEditingController(text: '${post['text']}');
    final v = await showSheet<String>(
      context,
      (ctx) => Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Text('Edit post', style: T.h2),
        const SizedBox(height: 12),
        LabeledField(label: 'Text', controller: c, lines: 10),
        const SizedBox(height: 14),
        PrimaryButton(label: 'Save', onTap: () => Navigator.pop(ctx, c.text)),
      ]),
    );
    c.dispose();
    if (v == null || !context.mounted) return;
    final r = await guarded(context, () => Session.I.api.put('/linkedin/posts/${post['id']}', data: {'text': v}), ok: 'Saved');
    if (r != null) onChanged();
  }

  @override
  Widget build(BuildContext context) {
    final published = post['status'] == 'published';
    return GlassCard(
      radius: R.md,
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(child: Text('${post['title'] ?? post['series'] ?? 'Post'}', maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w700))),
          Pill(prettyStatus('${post['status']}'), color: published ? C.good : (post['status'] == 'failed' ? C.bad : C.warn), filled: true),
        ]),
        const SizedBox(height: 8),
        Text('${post['text']}', maxLines: 6, overflow: TextOverflow.ellipsis, style: T.body.copyWith(fontSize: 14)),
        if (post['error'] != null) ...[const SizedBox(height: 6), Text('${post['error']}', style: TextStyle(color: C.bad, fontSize: 12.5))],
        const SizedBox(height: 12),
        if (published && post['url'] != null)
          PrimaryButton(label: 'View on LinkedIn', ghost: true, onTap: () => openUrl(context, '${post['url']}'))
        else if (!published)
          Row(children: [
            Expanded(
              child: connected
                  ? PrimaryButton(label: 'Approve and publish', onTap: () => _publish(context))
                  : PrimaryButton(
                      label: 'Copy and post',
                      icon: Icons.copy_rounded,
                      onTap: () async {
                        await copyText(context, '${post['text']}', done: 'Copied. Paste it into LinkedIn.');
                        if (post['share_url'] != null && context.mounted) await openUrl(context, '${post['share_url']}');
                      },
                    ),
            ),
            const SizedBox(width: 8),
            PrimaryButton(label: 'Edit', ghost: true, expand: false, onTap: () => _edit(context)),
          ]),
      ]),
    );
  }
}
