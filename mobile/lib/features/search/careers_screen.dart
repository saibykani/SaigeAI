import 'package:material_ui/material_ui.dart';

import '../../core/api.dart';
import '../../core/motion.dart';
import '../../core/resource.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/dot_ring.dart';
import '../../core/widgets/kit.dart';
import '../../core/widgets/ui.dart';
import 'open_job_card.dart';

/// Company career pages (Greenhouse, Lever, Ashby, Workday and more), scanned and scored for you.
class CareersScreen extends StatefulWidget {
  const CareersScreen({super.key});
  @override
  State<CareersScreen> createState() => _CareersScreenState();
}

class _CareersScreenState extends State<CareersScreen> {
  final _q = TextEditingController();
  final _scroll = ScrollController();
  List<Map<String, dynamic>> _items = [];
  Map<String, dynamic> _facets = {};
  Map<String, dynamic> _scan = {};
  int _total = 0;
  int _page = 1;
  bool _loading = true;
  bool _more = false;
  bool _scanning = false;
  ApiException? _error;
  String _sort = 'score';
  String _fit = 'all';
  String _scope = 'all';
  bool _remote = false;
  bool _fresh = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _q.dispose();
    _scroll.dispose();
    super.dispose();
  }

  Map<String, dynamic> get _query => {
        'page': _page,
        'page_size': 20,
        'sort': _sort,
        if (_q.text.trim().isNotEmpty) 'q': _q.text.trim(),
        if (_fit != 'all') 'fits': _fit,
        if (_scope != 'all') 'scopes': _scope,
        if (_remote) 'remote': true,
        if (_fresh) 'new_days': 2,
      };

  Future<void> _load({bool more = false}) async {
    if (more) {
      _page++;
    } else {
      _page = 1;
    }
    setState(() {
      _error = null;
      if (more) {
        _more = true;
      } else {
        _loading = true;
      }
    });
    try {
      final r = asMap(await Session.I.api.get('/careers/jobs', query: _query));
      if (!mounted) return;
      setState(() {
        final got = asList(r['items']);
        _items = more ? [..._items, ...got] : got;
        _total = (r['total'] as num?)?.toInt() ?? _items.length;
        _facets = asMap(r['facets']);
        _scan = asMap(r['scan']);
      });
    } on ApiException catch (e) {
      if (mounted) {
        setState(() => _error = e);
        if (more) _page--;
      }
    }
    if (mounted) {
      setState(() {
        _loading = false;
        _more = false;
      });
    }
  }

  Future<void> _runScan() async {
    setState(() => _scanning = true);
    try {
      final r = asMap(await Session.I.api.post('/careers/scan', data: <String, dynamic>{'companies': <String>[]}));
      success();
      if (mounted) toast(context, 'Scanned: ${r['found'] ?? 0} postings, ${r['new'] ?? 0} new.');
      await _load();
    } on ApiException catch (e) {
      if (mounted) toast(context, e.message, error: true);
    }
    if (mounted) setState(() => _scanning = false);
  }

  Future<bool> _save(Map<String, dynamic> j) async {
    try {
      await Session.I.api.post('/careers/jobs/${j['id']}/save');
      success();
      if (mounted) toast(context, 'Saved to your jobs.');
      return true;
    } on ApiException catch (e) {
      if (mounted) toast(context, e.message, error: true);
      return false;
    }
  }

  List<String> _facetOptions(String key) => ['all', ...asList(_facets[key]).map((f) => '${f['value']}')];

  @override
  Widget build(BuildContext context) {
    final scanLine = _scan.isEmpty
        ? 'Not scanned yet'
        : '${_scan['found'] ?? 0} found, ${_scan['new'] ?? 0} new  ·  ${timeAgo('${_scan['finished_at'] ?? ''}')}';
    return FeatureScaffold(
      title: 'Career portals',
      subtitle: scanLine,
      trailing: Pressable(
        onTap: _scanning ? null : _runScan,
        child: Container(
          width: 44,
          height: 44,
          decoration: BoxDecoration(shape: BoxShape.circle, color: C.primarySoft, border: Border.all(color: C.primary)),
          child: _scanning ? const Padding(padding: EdgeInsets.all(10), child: DotRing(size: 22, dots: 10)) : const Icon(Icons.radar_rounded, color: C.primary, size: 22),
        ),
      ),
      child: Column(children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 10),
          child: TextField(
            controller: _q,
            textInputAction: TextInputAction.search,
            onSubmitted: (_) => _load(),
            decoration: InputDecoration(
              hintText: 'Search title, company, skill',
              prefixIcon: const Icon(Icons.search_rounded, color: C.muted),
              suffixIcon: _q.text.isEmpty ? null : IconButton(icon: const Icon(Icons.close_rounded, color: C.muted), onPressed: () => setState(() {
                    _q.clear();
                    _load();
                  })),
              contentPadding: const EdgeInsets.symmetric(vertical: 14),
            ),
          ),
        ),
        ChipRow(options: const ['score', 'recent', 'new', 'company'], labels: const {'score': 'Best fit', 'recent': 'Recent', 'new': 'Newly found', 'company': 'Company'}, value: _sort, onChanged: (v) {
          _sort = v;
          _load();
        }),
        const SizedBox(height: 8),
        ChipRow(options: const ['all', 'strong', 'good', 'stretch'], labels: const {'all': 'Any fit', 'strong': 'Strong', 'good': 'Good', 'stretch': 'Stretch'}, value: _fit, onChanged: (v) {
          _fit = v;
          _load();
        }),
        const SizedBox(height: 8),
        ChipRow(options: _facetOptions('scopes'), labels: const {'all': 'Anywhere', 'country': 'My country', 'remote': 'Remote', 'abroad': 'Abroad'}, value: _scope, onChanged: (v) {
          _scope = v;
          _load();
        }),
        const SizedBox(height: 8),
        SizedBox(
          height: 40,
          child: ListView(scrollDirection: Axis.horizontal, padding: const EdgeInsets.symmetric(horizontal: 20), physics: const BouncingScrollPhysics(), children: [
            _Toggle('Remote only', _remote, (v) {
              _remote = v;
              _load();
            }),
            const SizedBox(width: 8),
            _Toggle('Posted in last 2 days', _fresh, (v) {
              _fresh = v;
              _load();
            }),
          ]),
        ),
        const SizedBox(height: 6),
        Expanded(child: _body()),
      ]),
    );
  }

  Widget _body() {
    if (_loading && _items.isEmpty) return const LoadingState();
    if (_error != null && _items.isEmpty) return ErrorState(error: _error!, onRetry: _load);
    if (_items.isEmpty) {
      return EmptyState(
        icon: Icons.business_center_outlined,
        title: _scan.isEmpty ? 'Scan the career pages' : 'No jobs match these filters',
        body: _scan.isEmpty ? 'Saige checks 65+ company career pages and scores every opening against your profile.' : 'Loosen a filter, or scan again for fresh postings.',
        action: _scan.isEmpty ? 'Scan now' : null,
        onAction: _runScan,
      );
    }
    return ListView.builder(
      controller: _scroll,
      physics: const BouncingScrollPhysics(),
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 120),
      itemCount: _items.length + 1,
      itemBuilder: (context, i) {
        if (i == _items.length) {
          if (_items.length >= _total) return Padding(padding: const EdgeInsets.all(16), child: Center(child: Text('$_total jobs', style: T.small)));
          return Padding(padding: const EdgeInsets.only(top: 6), child: PrimaryButton(label: 'Load more', ghost: true, busy: _more, onTap: () => _load(more: true)));
        }
        final j = _items[i];
        return Padding(
          padding: const EdgeInsets.only(bottom: 12),
          child: Stagger(index: i % 8, child: OpenJobCard(key: ValueKey(j['id']), job: j, saved: j['saved_job_id'] != null, onSave: () => _save(j))),
        );
      },
    );
  }
}

class _Toggle extends StatelessWidget {
  const _Toggle(this.label, this.on, this.onChanged);
  final String label;
  final bool on;
  final ValueChanged<bool> onChanged;
  @override
  Widget build(BuildContext context) => Pressable(
        onTap: () => onChanged(!on),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 220),
          padding: const EdgeInsets.symmetric(horizontal: 14),
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: on ? C.primarySoft : C.surface2,
            borderRadius: BorderRadius.circular(99),
            border: Border.all(color: on ? C.primary : C.line),
          ),
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            Icon(on ? Icons.check_rounded : Icons.add_rounded, size: 16, color: on ? C.primary : C.muted),
            const SizedBox(width: 6),
            Text(label, style: TextStyle(color: on ? C.primary : C.muted, fontWeight: FontWeight.w600, fontSize: 13)),
          ]),
        ),
      );
}
