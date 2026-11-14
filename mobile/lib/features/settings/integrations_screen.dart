import 'package:material_ui/material_ui.dart';

import '../../core/motion.dart';
import '../../core/resource.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/forms.dart';
import '../../core/widgets/kit.dart';
import '../../core/widgets/ui.dart';

/// Connection status for Gmail, WhatsApp and the rest. OAuth-only connections open the web app.
class IntegrationsScreen extends StatefulWidget {
  const IntegrationsScreen({super.key});
  @override
  State<IntegrationsScreen> createState() => _IntegrationsScreenState();
}

class _IntegrationsScreenState extends State<IntegrationsScreen> {
  final _r = Resource<Map<String, dynamic>>(() async => asMap(await Session.I.api.get('/integrations')));

  @override
  void initState() {
    super.initState();
    _r.load();
  }

  @override
  void dispose() {
    _r.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => FeatureScaffold(
        title: 'Integrations',
        subtitle: 'What Saige is connected to',
        child: ResourceView<Map<String, dynamic>>(
          resource: _r,
          builder: (context, d) {
            final g = asMap(d['gmail']);
            final wa = asMap(d['whatsapp']);
            final cl = asMap(d['claude']);
            final items = <(IconData, Color, String, String, bool, String?)>[
              (Icons.mail_rounded, C.bad, 'Gmail', g['connected'] == true ? '${g['email'] ?? 'Connected'}${g['last_sync_at'] != null ? '  ·  synced ${timeAgo('${g['last_sync_at']}')}' : ''}' : 'Reads recruiter replies and sends approved mail', g['connected'] == true, '/integrations'),
              (Icons.chat_rounded, C.good, 'WhatsApp alerts', wa['connected'] == true ? '${wa['phone'] ?? 'Connected'}  ·  ${wa['enabled'] == true ? 'on' : 'paused'}' : 'Mirror alerts to WhatsApp (CallMeBot)', wa['connected'] == true, '/integrations'),
              (Icons.send_rounded, C.blue, 'Telegram alerts', 'Link your Telegram from the web app', false, '/integrations'),
              (Icons.notifications_active_rounded, C.warn, 'Phone push', 'This app shows alerts in Notifications. System push is not set up yet', false, null),
              (Icons.login_rounded, C.violet, 'Google sign-in', asMap(d['google'])['connected'] == true ? 'Linked to your account' : 'Not linked', asMap(d['google'])['connected'] == true, null),
              (Icons.auto_awesome_rounded, C.teal, 'Saige AI (Claude)', cl['enabled'] == true ? 'Enabled  ·  ${cl['model']}' : 'Built-in answers, no model key on the server', cl['enabled'] == true, null),
              (Icons.work_rounded, C.blue, 'LinkedIn profile', 'Copy-ready edits, you apply them', asMap(d['linkedin'])['snapshot'] == true, null),
              (Icons.badge_rounded, C.lime, 'Naukri profile', 'Copy-ready edits, you apply them', asMap(d['naukri'])['snapshot'] == true, null),
            ];
            return RefreshIndicatorList(onRefresh: _r.load, children: [
              for (final (i, it) in items.indexed)
                Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: Stagger(
                    index: i % 8,
                    child: GlassCard(
                      radius: R.md,
                      padding: const EdgeInsets.all(14),
                      onTap: it.$6 == null ? null : () => openUrl(context, webUrl(it.$6!)),
                      child: Row(children: [
                        IconBadge(it.$1, it.$2),
                        const SizedBox(width: 12),
                        Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(it.$3, style: const TextStyle(fontWeight: FontWeight.w700)), Text(it.$4, maxLines: 2, overflow: TextOverflow.ellipsis, style: T.small)])),
                        Pill(it.$5 ? 'Connected' : 'Not connected', color: it.$5 ? C.good : C.muted, filled: it.$5),
                      ]),
                    ),
                  ),
                ),
              const SizedBox(height: 6),
              Text('Connections that need Google or LinkedIn sign-in open the web app in your browser.', style: T.small, textAlign: TextAlign.center),
            ]);
          },
        ),
      );
}
