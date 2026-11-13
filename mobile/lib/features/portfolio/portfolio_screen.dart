import 'package:material_ui/material_ui.dart';

import '../../core/motion.dart';
import '../../core/resource.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/forms.dart';
import '../../core/widgets/kit.dart';
import '../../core/widgets/ui.dart';

Color _hex(dynamic v, Color fallback) {
  final s = '$v'.replaceAll('#', '');
  final n = int.tryParse(s.length == 6 ? 'FF$s' : s, radix: 16);
  return n == null ? fallback : Color(n);
}

/// Portfolio builder: pick a template, set the slug and toggles, publish and share. The page is
/// rendered live from your verified profile on the server.
class PortfolioScreen extends StatefulWidget {
  const PortfolioScreen({super.key});
  @override
  State<PortfolioScreen> createState() => _PortfolioScreenState();
}

class _PortfolioScreenState extends State<PortfolioScreen> {
  final _tpl = Resource<List<Map<String, dynamic>>>(() async => asList(await Session.I.api.get('/portfolio/templates')));
  final _cfg = Resource<Map<String, dynamic>>(() async => asMap(await Session.I.api.get('/portfolio')));
  final _slug = TextEditingController();
  final _tag = TextEditingController();
  String _template = '';
  bool _email = true, _phone = false, _open = true;
  bool _busy = false, _loaded = false;

  @override
  void initState() {
    super.initState();
    _tpl.load();
    _cfg.load().then((_) => _fill());
  }

  void _fill() {
    final c = _cfg.data;
    if (c == null || !mounted) return;
    setState(() {
      _slug.text = '${c['slug']}';
      _tag.text = '${c['tagline']}';
      _template = '${c['template']}';
      _email = c['show_email'] == true;
      _phone = c['show_phone'] == true;
      _open = c['open_to_work'] == true;
      _loaded = true;
    });
  }

  @override
  void dispose() {
    _tpl.dispose();
    _cfg.dispose();
    _slug.dispose();
    _tag.dispose();
    super.dispose();
  }

  Map<String, dynamic> get _body => {'template': _template, 'slug': _slug.text.trim().toLowerCase(), 'tagline': _tag.text.trim(), 'show_email': _email, 'show_phone': _phone, 'open_to_work': _open};

  String get _publicUrl => webUrl('/p/${_slug.text.trim().toLowerCase()}');

  Future<void> _run(Future<dynamic> Function() f, String ok) async {
    setState(() => _busy = true);
    final r = await guarded(context, f, ok: ok);
    if (!mounted) return;
    setState(() => _busy = false);
    if (r != null) {
      success();
      _cfg.set(asMap(r));
      _fill();
    }
  }

  @override
  Widget build(BuildContext context) => FeatureScaffold(
        title: 'Portfolio',
        subtitle: 'A page built from your verified profile',
        child: ListenableBuilder(
          listenable: Listenable.merge([_tpl, _cfg]),
          builder: (context, _) {
            if (!_loaded || _tpl.data == null) {
              final e = _cfg.error ?? _tpl.error;
              return e != null ? ErrorState(error: e, onRetry: () { _cfg.load().then((_) => _fill()); _tpl.load(); }) : const LoadingState();
            }
            final published = _cfg.data?['published'] == true;
            return ListView(physics: const BouncingScrollPhysics(), padding: const EdgeInsets.fromLTRB(20, 4, 20, 120), children: [
              Stagger(
                index: 0,
                child: GlassCard(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Row(children: [
                      IconBadge(published ? Icons.public_rounded : Icons.public_off_rounded, published ? C.good : C.muted),
                      const SizedBox(width: 12),
                      Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(published ? 'Live' : 'Not published', style: const TextStyle(fontWeight: FontWeight.w700)), Text(published ? '${_cfg.data?['views'] ?? 0} views' : 'Only you can see it', style: T.small)])),
                    ]),
                    if (published) ...[
                      const SizedBox(height: 12),
                      Container(padding: const EdgeInsets.all(12), decoration: BoxDecoration(color: C.surface2, borderRadius: BorderRadius.circular(R.sm)), child: Text(_publicUrl, style: T.small.copyWith(color: C.text))),
                      const SizedBox(height: 10),
                      Row(children: [
                        Expanded(child: PrimaryButton(label: 'Open', icon: Icons.open_in_new_rounded, onTap: () => openUrl(context, _publicUrl))),
                        const SizedBox(width: 8),
                        Expanded(child: PrimaryButton(label: 'Copy link', ghost: true, icon: Icons.copy_rounded, onTap: () => copyText(context, _publicUrl, done: 'Link copied'))),
                      ]),
                    ],
                  ]),
                ),
              ),
              const SectionTitle('Template'),
              SizedBox(
                height: 118,
                child: ListView.separated(
                  scrollDirection: Axis.horizontal,
                  physics: const BouncingScrollPhysics(),
                  itemCount: _tpl.data!.length,
                  separatorBuilder: (_, _) => const SizedBox(width: 10),
                  itemBuilder: (context, i) {
                    final t = _tpl.data![i];
                    final on = t['id'] == _template;
                    final cols = ((t['colors'] as List?) ?? []).map((c) => _hex(c, C.surface3)).toList();
                    return Pressable(
                      onTap: () => setState(() => _template = '${t['id']}'),
                      child: AnimatedContainer(
                        duration: const Duration(milliseconds: 250),
                        width: 132,
                        padding: const EdgeInsets.all(10),
                        decoration: BoxDecoration(color: C.surface, borderRadius: BorderRadius.circular(R.md), border: Border.all(color: on ? C.primary : C.line, width: on ? 2 : 1), boxShadow: C.shadow),
                        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          Expanded(child: ClipRRect(borderRadius: BorderRadius.circular(10), child: Row(children: [for (final c in cols.take(4)) Expanded(child: ColoredBox(color: c, child: const SizedBox.expand()))]))),
                          const SizedBox(height: 8),
                          Text('${t['name']}', maxLines: 1, overflow: TextOverflow.ellipsis, style: TextStyle(fontWeight: FontWeight.w700, fontSize: 13, color: on ? C.primary : C.text)),
                        ]),
                      ),
                    );
                  },
                ),
              ),
              const SectionTitle('Settings'),
              LabeledField(label: 'Link name', controller: _slug, hint: 'asha-rao'),
              const SizedBox(height: 12),
              LabeledField(label: 'Tagline', controller: _tag, hint: 'One line about you'),
              const SizedBox(height: 14),
              RowsCard(children: [
                ToggleRow(title: 'Show email', value: _email, onChanged: (v) => setState(() => _email = v)),
                ToggleRow(title: 'Show phone', value: _phone, onChanged: (v) => setState(() => _phone = v)),
                ToggleRow(title: 'Open to work badge', value: _open, onChanged: (v) => setState(() => _open = v)),
              ]),
              const SizedBox(height: 18),
              PrimaryButton(label: published ? 'Save and update' : 'Publish portfolio', icon: Icons.rocket_launch_rounded, busy: _busy, onTap: () => _run(() => Session.I.api.post('/portfolio/publish', data: _body), published ? 'Updated' : 'Your portfolio is live')),
              const SizedBox(height: 8),
              PrimaryButton(label: 'Save draft only', ghost: true, onTap: () => _run(() => Session.I.api.put('/portfolio', data: _body), 'Saved')),
              if (published) ...[
                const SizedBox(height: 8),
                PrimaryButton(label: 'Unpublish', ghost: true, onTap: () => _run(() => Session.I.api.post('/portfolio/unpublish'), 'Unpublished')),
              ],
              const SizedBox(height: 12),
              Text('Preview opens in the browser once published. Your portfolio only shows facts from your verified profile.', style: T.small, textAlign: TextAlign.center),
            ]);
          },
        ),
      );
}
