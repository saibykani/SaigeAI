import 'package:material_ui/material_ui.dart';

import '../../core/api.dart';
import '../../core/google_auth.dart';
import '../../core/motion.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/logo.dart';

/// Sign in / create account, designed like a Google or Apple account screen: calm, white (or dark) surface,
/// the logo, one clear title, "Continue with Google", then email and password. No intro animation: the screen is
/// ready instantly. The celebration happens after sign-in (see the welcome transition in the app shell).
class AuthScreen extends StatefulWidget {
  const AuthScreen({super.key});
  @override
  State<AuthScreen> createState() => _AuthScreenState();
}

class _AuthScreenState extends State<AuthScreen> {
  final _name = TextEditingController();
  final _email = TextEditingController();
  final _pass = TextEditingController();
  bool _register = false;
  bool _busy = false;
  bool _hide = true;
  String _role = 'jobseeker';
  String? _error;

  @override
  void dispose() {
    _name.dispose();
    _email.dispose();
    _pass.dispose();
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
      if (mounted) setState(() => _busy = false);
    } on ApiException catch (e) {
      _fail(e.message);
    } catch (_) {
      _fail('Could not sign in. Check your connection and try again.');
    }
  }

  Future<void> _google() async {
    FocusScope.of(context).unfocus();
    if (!GoogleAuth.configured) {
      _fail('Google sign-in is not set up in this build yet.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final token = await GoogleAuth.idToken();
      if (token == null) {
        if (mounted) setState(() => _busy = false);
        return;
      }
      await Session.I.loginWithGoogle(token, role: _register ? _role : 'jobseeker');
      if (mounted) setState(() => _busy = false);
    } on ApiException catch (e) {
      _fail(e.message);
    } catch (_) {
      _fail('Google sign-in did not work. Check your connection and try again.');
    }
  }

  void _fail(String m) {
    tap();
    if (mounted) {
      setState(() {
        _error = m;
        _busy = false;
      });
    }
  }

  InputDecoration _deco(String label, {Widget? suffix}) => InputDecoration(
        labelText: label,
        suffixIcon: suffix,
        filled: true,
        fillColor: C.surface2,
        contentPadding: const EdgeInsets.symmetric(horizontal: 18, vertical: 18),
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: BorderSide(color: C.line)),
        enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: BorderSide(color: C.line)),
        focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: BorderSide(color: C.primary, width: 2)),
        labelStyle: TextStyle(color: C.muted),
      );

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: C.bg,
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 440),
            child: ListView(
              padding: const EdgeInsets.fromLTRB(28, 48, 28, 28),
              shrinkWrap: true,
              children: [
                const Center(child: LogoMark(size: 56, radius: 0.26)),
                const SizedBox(height: 28),
                Text(_register ? 'Create your account' : 'Sign in', textAlign: TextAlign.center,
                    style: TextStyle(fontSize: 28, fontWeight: FontWeight.w600, letterSpacing: -0.6, color: C.text)),
                const SizedBox(height: 8),
                Text(_register ? 'to start your search with Saige AI' : 'to continue to Saige AI', textAlign: TextAlign.center,
                    style: TextStyle(fontSize: 15.5, color: C.muted)),
                const SizedBox(height: 32),
                if (_register) ...[
                  SegmentedButton<String>(
                    segments: const [
                      ButtonSegment(value: 'jobseeker', label: Text('Job seeker'), icon: Icon(Icons.person_search_rounded)),
                      ButtonSegment(value: 'recruiter', label: Text('Recruiter'), icon: Icon(Icons.groups_rounded)),
                    ],
                    selected: {_role},
                    onSelectionChanged: (s) => setState(() => _role = s.first),
                    showSelectedIcon: false,
                  ),
                  const SizedBox(height: 20),
                ],
                _GoogleButton(busy: _busy, onTap: _google),
                const SizedBox(height: 22),
                Row(children: [
                  Expanded(child: Divider(color: C.line)),
                  Padding(padding: const EdgeInsets.symmetric(horizontal: 12), child: Text('or', style: TextStyle(color: C.muted))),
                  Expanded(child: Divider(color: C.line)),
                ]),
                const SizedBox(height: 22),
                if (_register) ...[
                  TextField(controller: _name, textCapitalization: TextCapitalization.words, textInputAction: TextInputAction.next,
                      autofillHints: const [AutofillHints.name], decoration: _deco('Full name')),
                  const SizedBox(height: 14),
                ],
                TextField(controller: _email, keyboardType: TextInputType.emailAddress, textInputAction: TextInputAction.next,
                    autofillHints: const [AutofillHints.email], decoration: _deco('Email')),
                const SizedBox(height: 14),
                TextField(
                  controller: _pass,
                  obscureText: _hide,
                  textInputAction: TextInputAction.done,
                  onSubmitted: (_) => _submit(),
                  autofillHints: [_register ? AutofillHints.newPassword : AutofillHints.password],
                  decoration: _deco('Password',
                      suffix: IconButton(
                        icon: Icon(_hide ? Icons.visibility_outlined : Icons.visibility_off_outlined, color: C.muted),
                        onPressed: () => setState(() => _hide = !_hide),
                      )),
                ),
                if (_error != null) ...[
                  const SizedBox(height: 14),
                  Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Icon(Icons.error_outline_rounded, size: 18, color: C.bad),
                    const SizedBox(width: 8),
                    Expanded(child: Text(_error!, style: TextStyle(color: C.bad, fontSize: 13.5))),
                  ]),
                ],
                const SizedBox(height: 24),
                SizedBox(
                  height: 52,
                  child: FilledButton(
                    onPressed: _busy ? null : _submit,
                    style: FilledButton.styleFrom(shape: const StadiumBorder(), textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
                    child: _busy
                        ? SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2.4, color: C.onPrimary))
                        : Text(_register ? 'Create account' : 'Sign in'),
                  ),
                ),
                const SizedBox(height: 12),
                TextButton(
                  onPressed: _busy ? null : () => setState(() {
                    _register = !_register;
                    _error = null;
                  }),
                  child: Text(_register ? 'Already have an account? Sign in' : 'New to Saige? Create account'),
                ),
                const SizedBox(height: 28),
                Text('Nothing is sent or applied without your approval.', textAlign: TextAlign.center,
                    style: TextStyle(fontSize: 12.5, color: C.muted)),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _GoogleButton extends StatelessWidget {
  const _GoogleButton({required this.busy, required this.onTap});
  final bool busy;
  final VoidCallback onTap;
  @override
  Widget build(BuildContext context) => SizedBox(
        height: 52,
        child: OutlinedButton(
          onPressed: busy ? null : onTap,
          style: OutlinedButton.styleFrom(
            shape: const StadiumBorder(),
            side: BorderSide(color: C.line),
            backgroundColor: C.dark ? const Color(0xFF131314) : Colors.white,
            foregroundColor: C.dark ? const Color(0xFFE3E3E3) : const Color(0xFF1F1F1F),
          ),
          child: const Row(mainAxisAlignment: MainAxisAlignment.center, children: [
            SizedBox(width: 20, height: 20, child: CustomPaint(painter: _GoogleG())),
            SizedBox(width: 12),
            Flexible(child: Text('Continue with Google', maxLines: 1, overflow: TextOverflow.ellipsis, style: TextStyle(fontSize: 15.5, fontWeight: FontWeight.w600))),
          ]),
        ),
      );
}

/// Multicolour Google "G" built from four arcs and the crossbar.
class _GoogleG extends CustomPainter {
  const _GoogleG();
  @override
  void paint(Canvas canvas, Size size) {
    final s = size.width;
    final c = Offset(s / 2, s / 2);
    final stroke = s * 0.2;
    final rect = Rect.fromCircle(center: c, radius: s / 2 - stroke / 2);
    Paint p(Color col) => Paint()
      ..color = col
      ..style = PaintingStyle.stroke
      ..strokeWidth = stroke;
    const pi = 3.141592653589793;
    canvas.drawArc(rect, -pi * 0.75, pi * 0.5, false, p(const Color(0xFFEA4335)));
    canvas.drawArc(rect, pi * 0.75, pi * 0.5, false, p(const Color(0xFFFBBC05)));
    canvas.drawArc(rect, pi * 0.25, pi * 0.5, false, p(const Color(0xFF34A853)));
    final blue = Paint()..color = const Color(0xFF4285F4);
    canvas.drawRect(Rect.fromLTRB(s * 0.5, s * 0.4, s * 0.98, s * 0.6), blue);
    canvas.drawArc(rect, 0, pi * 0.25, false, p(const Color(0xFF4285F4)));
  }

  @override
  bool shouldRepaint(covariant CustomPainter old) => false;
}
