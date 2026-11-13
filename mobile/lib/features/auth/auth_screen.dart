import 'package:material_ui/material_ui.dart';

import '../../core/api.dart';
import '../../core/motion.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/logo.dart';
import '../../core/widgets/galaxy.dart';
import '../../core/widgets/ui.dart';

/// Cinematic sign-in / sign-up over a tilt-reactive particle field.
/// TODO: Google sign-in (needs a native OAuth client + a token-exchange endpoint on the API).
class AuthScreen extends StatefulWidget {
  const AuthScreen({super.key});
  @override
  State<AuthScreen> createState() => _AuthScreenState();
}

class _AuthScreenState extends State<AuthScreen> with SingleTickerProviderStateMixin {
  final _name = TextEditingController();
  final _email = TextEditingController();
  final _pass = TextEditingController();
  bool _register = false;
  bool _busy = false;
  bool _hide = true;
  String _role = 'jobseeker';
  String? _error;
  late final AnimationController _shake = AnimationController(vsync: this, duration: const Duration(milliseconds: 420));

  @override
  void dispose() {
    _name.dispose();
    _email.dispose();
    _pass.dispose();
    _shake.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    FocusScope.of(context).unfocus();
    final email = _email.text.trim();
    if (!email.contains('@') || _pass.text.isEmpty || (_register && (_name.text.trim().isEmpty || _pass.text.length < 8))) {
      _fail(_register ? 'Add your name, a valid email and a password of 8+ characters.' : 'Enter your email and password.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      if (_register) {
        await Session.I.register(name: _name.text, email: email, password: _pass.text, role: _role);
      } else {
        await Session.I.login(email, _pass.text);
      }
      success();
    } on ApiException catch (e) {
      _fail(e.message);
    } catch (_) {
      _fail('Could not sign in. Check your connection and try again.');
    }
  }

  void _fail(String m) {
    thump();
    _shake.forward(from: 0);
    if (mounted) {
      setState(() {
        _error = m;
        _busy = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        backgroundColor: C.bg,
        resizeToAvoidBottomInset: true,
        body: GalaxyBackground(
          child: SafeArea(
            child: Center(
              child: SingleChildScrollView(
                padding: const EdgeInsets.fromLTRB(22, 20, 22, 20),
                child: Column(mainAxisSize: MainAxisSize.min, children: [
                  const Stagger(index: 0, child: LogoMark(size: 72, radius: 0.26)),
                  const SizedBox(height: 18),
                  const Stagger(index: 1, child: Text('Saige AI', style: T.display)),
                  const SizedBox(height: 6),
                  Stagger(index: 2, child: Text(_register ? 'Create your career copilot' : 'Welcome back. Your search, handled truthfully.', style: T.small, textAlign: TextAlign.center)),
                  const SizedBox(height: 28),
                  Stagger(
                    index: 3,
                    child: AnimatedBuilder(
                      animation: _shake,
                      builder: (context, child) => Transform.translate(
                        offset: Offset(12 * (1 - _shake.value) * (_shake.value == 0 ? 0 : (((_shake.value * 10).floor() % 2 == 0) ? 1 : -1)), 0),
                        child: child,
                      ),
                      child: GlassCard(
                        padding: const EdgeInsets.all(20),
                        child: AnimatedSize(
                          duration: const Duration(milliseconds: 420),
                          curve: softSpring,
                          alignment: Alignment.topCenter,
                          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                            _ModeSwitch(register: _register, onChanged: (v) => setState(() {
                              _register = v;
                              _error = null;
                            })),
                            const SizedBox(height: 18),
                            if (_register) ...[
                              TextField(controller: _name, textCapitalization: TextCapitalization.words, decoration: const InputDecoration(hintText: 'Full name')),
                              const SizedBox(height: 12),
                            ],
                            TextField(controller: _email, keyboardType: TextInputType.emailAddress, autofillHints: const [AutofillHints.email], decoration: const InputDecoration(hintText: 'Email')),
                            const SizedBox(height: 12),
                            TextField(
                              controller: _pass,
                              obscureText: _hide,
                              onSubmitted: (_) => _submit(),
                              decoration: InputDecoration(
                                hintText: 'Password',
                                suffixIcon: IconButton(icon: Icon(_hide ? Icons.visibility_off_outlined : Icons.visibility_outlined, color: C.muted), onPressed: () => setState(() => _hide = !_hide)),
                              ),
                            ),
                            if (_register) ...[
                              const SizedBox(height: 16),
                              const Text('I AM A', style: T.label),
                              const SizedBox(height: 8),
                              Row(children: [
                                Expanded(child: _RoleChip(label: 'Job seeker', icon: Icons.person_search_rounded, on: _role == 'jobseeker', onTap: () => setState(() => _role = 'jobseeker'))),
                                const SizedBox(width: 10),
                                Expanded(child: _RoleChip(label: 'Recruiter', icon: Icons.groups_rounded, on: _role == 'recruiter', onTap: () => setState(() => _role = 'recruiter'))),
                              ]),
                            ],
                            if (_error != null) ...[
                              const SizedBox(height: 14),
                              Text(_error!, style: const TextStyle(color: C.bad, fontSize: 13.5)),
                            ],
                            const SizedBox(height: 20),
                            PrimaryButton(label: _register ? 'Create account' : 'Sign in', busy: _busy, onTap: _submit),
                          ]),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 18),
                  const Stagger(index: 5, child: Text('Nothing is sent or applied without your approval.', style: T.small, textAlign: TextAlign.center)),
                ]),
              ),
            ),
          ),
        ),
      );
}

class _ModeSwitch extends StatelessWidget {
  const _ModeSwitch({required this.register, required this.onChanged});
  final bool register;
  final ValueChanged<bool> onChanged;
  @override
  Widget build(BuildContext context) => Container(
        height: 46,
        padding: const EdgeInsets.all(4),
        decoration: BoxDecoration(color: C.surface2, borderRadius: BorderRadius.circular(R.md)),
        child: Stack(children: [
          AnimatedAlign(
            duration: const Duration(milliseconds: 450),
            curve: springy,
            alignment: register ? Alignment.centerRight : Alignment.centerLeft,
            child: FractionallySizedBox(widthFactor: 0.5, child: Container(decoration: BoxDecoration(color: C.primary, borderRadius: BorderRadius.circular(R.sm)))),
          ),
          Row(children: [
            for (final (i, l) in ['Sign in', 'Sign up'].indexed)
              Expanded(
                child: Pressable(
                  scale: 0.97,
                  onTap: () => onChanged(i == 1),
                  child: Center(child: Text(l, style: TextStyle(fontWeight: FontWeight.w600, color: (register == (i == 1)) ? Colors.white : C.muted))),
                ),
              ),
          ]),
        ]),
      );
}

class _RoleChip extends StatelessWidget {
  const _RoleChip({required this.label, required this.icon, required this.on, required this.onTap});
  final String label;
  final IconData icon;
  final bool on;
  final VoidCallback onTap;
  @override
  Widget build(BuildContext context) => Pressable(
        onTap: onTap,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 250),
          padding: const EdgeInsets.symmetric(vertical: 14),
          decoration: BoxDecoration(
            color: on ? C.primarySoft : C.surface2,
            borderRadius: BorderRadius.circular(R.md),
            border: Border.all(color: on ? C.primary : C.line, width: on ? 1.4 : 1),
          ),
          child: Column(children: [Icon(icon, color: on ? C.primary : C.muted), const SizedBox(height: 4), Text(label, style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: on ? C.text : C.muted))]),
        ),
      );
}
