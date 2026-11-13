import 'package:material_ui/material_ui.dart';

import '../../core/motion.dart';
import '../../core/resource.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/kit.dart';
import '../../core/widgets/ui.dart';

/// Horizontal carousel of the user's resumes; selects the first by default.
class ResumePicker extends StatefulWidget {
  const ResumePicker({super.key, required this.onSelected});
  final void Function(String id, String name) onSelected;
  @override
  State<ResumePicker> createState() => _ResumePickerState();
}

class _ResumePickerState extends State<ResumePicker> {
  final _r = Resource<List<Map<String, dynamic>>>(() async => asList(await Session.I.api.get('/resumes')));
  String? _sel;

  @override
  void initState() {
    super.initState();
    _r.load().then((_) {
      final l = _r.data;
      if (mounted && l != null && l.isNotEmpty) _pick(l.first);
    });
  }

  @override
  void dispose() {
    _r.dispose();
    super.dispose();
  }

  void _pick(Map<String, dynamic> r) {
    setState(() => _sel = '${r['id']}');
    widget.onSelected('${r['id']}', '${r['name']}');
  }

  @override
  Widget build(BuildContext context) => ListenableBuilder(
        listenable: _r,
        builder: (context, _) {
          final l = _r.data;
          if (l == null) return _r.error != null ? ErrorState(error: _r.error!, onRetry: _r.load) : const Busy();
          if (l.isEmpty) {
            return const GlassCard(child: Row(children: [Icon(Icons.upload_file_rounded, color: C.primary), SizedBox(width: 12), Expanded(child: Text('Upload a resume in Profile first. Saige works only from your real resume.', style: T.small))]));
          }
          return SizedBox(
            height: 92,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              clipBehavior: Clip.none,
              physics: const BouncingScrollPhysics(),
              itemCount: l.length,
              separatorBuilder: (_, _) => const SizedBox(width: 10),
              itemBuilder: (context, i) {
                final r = l[i];
                final on = '${r['id']}' == _sel;
                return Stagger(
                  index: i,
                  dx: 24,
                  child: Pressable(
                    onTap: () => _pick(r),
                    child: AnimatedContainer(
                      duration: const Duration(milliseconds: 250),
                      curve: Curves.easeOutCubic,
                      width: 190,
                      padding: const EdgeInsets.all(14),
                      decoration: BoxDecoration(
                        color: on ? C.primarySoft : C.surface,
                        borderRadius: BorderRadius.circular(R.md),
                        border: Border.all(color: on ? C.primary : C.line, width: on ? 1.5 : 1),
                      ),
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisAlignment: MainAxisAlignment.center, children: [
                        Icon(on ? Icons.check_circle_rounded : Icons.description_outlined, color: on ? C.primary : C.muted, size: 20),
                        const SizedBox(height: 8),
                        Text('${r['name']}', maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w600)),
                        Text('${r['kind'] ?? ''}', maxLines: 1, overflow: TextOverflow.ellipsis, style: T.small),
                      ]),
                    ),
                  ),
                );
              },
            ),
          );
        },
      );
}
