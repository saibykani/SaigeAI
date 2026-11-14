import 'dart:ui' as ui;

import 'package:material_ui/material_ui.dart';

import '../../core/api.dart';
import '../../core/google_auth.dart';
import '../../core/motion.dart';
import '../../core/session.dart';
import '../../core/widgets/galaxy.dart';
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

  // The sign-in always sits on the night sky, so it uses its own light-on-dark palette whatever the app theme is.
  static const _txt = Colors.white;
  static final _sub = Colors.white.withValues(alpha: 0.68);
  static final _edge = Colors.white.withValues(alpha: 0.16);

  InputDecoration _deco(String label, IconData icon, {Widget? suffix}) => InputDecoration(
        labelText: label,
        prefixIcon: Icon(icon, color: _sub, size: 20),
        suffixIcon: suffix,
        filled: true,
        fillColor: Colors.white.withValues(alpha: 0.07),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: BorderSide(color: _edge)),
        enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: BorderSide(color: _edge)),
        focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: const BorderSide(color: Colors.white, width: 1.6)),
        labelStyle: TextStyle(color: _sub),
        floatingLabelStyle: const TextStyle(color: Colors.white),
      );

  Widget _fadeIn(int i, Widget child) => TweenAnimationBuilder<double>(
        tween: Tween(begin: 0, end: 1),
        duration: Duration(milliseconds: 520 + i * 90),
        curve: Curves.easeOutCubic,
        builder: (context, v, c) => Opacity(opacity: v, child: Transform.translate(offset: Offset(0, 22 * (1 - v)), child: c)),
        child: child,
      );

  @override
  Widget build(BuildContext context) {
    final kb = MediaQuery.viewInsetsOf(context).bottom > 0;
    return Theme(
      data: ThemeData.dark(useMaterial3: true).copyWith(
        colorScheme: const ColorScheme.dark(primary: Colors.white, onPrimary: Colors.black, surface: Color(0xFF101014)),
        textSelectionTheme: const TextSelectionThemeData(cursorColor: Colors.white),
      ),
      child: Scaffold(
        backgroundColor: Colors.black,
        resizeToAvoidBottomInset: true,
        body: GalaxyBackground(
          child: SafeArea(
            child: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 460),
                child: ListView(
                  padding: const EdgeInsets.fromLTRB(20, 18, 20, 20),
                  shrinkWrap: true,
                  children: [
                    AnimatedSize(
                      duration: const Duration(milliseconds: 300),
                      child: kb
                          ? const SizedBox.shrink()
                          : _fadeIn(0, Column(children: [
                              const LogoMark(size: 64, radius: 0.26),
                              const SizedBox(height: 14),
                              const Text('Saige AI', style: TextStyle(color: _txt, fontSize: 30, fontWeight: FontWeight.w700, letterSpacing: -0.6)),
                              const SizedBox(height: 4),
                              Text('Your truthful AI career agent', style: TextStyle(color: _sub, fontSize: 14.5)),
                              const SizedBox(height: 14),
                              const Wrap(alignment: WrapAlignment.center, spacing: 8, runSpacing: 8, children: [
                                _Chip(Icons.auto_awesome_rounded, 'Smart job matches'),
                                _Chip(Icons.description_rounded, 'ATS-ready resumes'),
                                _Chip(Icons.verified_user_rounded, 'You approve every send'),
                              ]),
                              const SizedBox(height: 22),
                            ])),
                    ),
                    _fadeIn(1, ClipRRect(
                      borderRadius: BorderRadius.circular(28),
                      child: BackdropFilter(
                        filter: ui.ImageFilter.blur(sigmaX: 18, sigmaY: 18),
                        child: Container(
                          padding: const EdgeInsets.fromLTRB(22, 24, 22, 18),
                          decoration: BoxDecoration(
                            color: const Color(0xFF0B0B12).withValues(alpha: 0.62),
                            borderRadius: BorderRadius.circular(28),
                            border: Border.all(color: _edge),
                          ),
                          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                            AnimatedSwitcher(
                              duration: const Duration(milliseconds: 260),
                              child: Column(key: ValueKey(_register), children: [
                                Text(_register ? 'Create your account' : 'Welcome back', textAlign: TextAlign.center,
                                    style: const TextStyle(color: _txt, fontSize: 24, fontWeight: FontWeight.w600, letterSpacing: -0.4)),
                                const SizedBox(height: 6),
                                Text(_register ? 'Free to start. Takes under a minute.' : 'Sign in to continue to Saige AI', textAlign: TextAlign.center,
                                    style: TextStyle(color: _sub, fontSize: 14.5)),
                              ]),
                            ),
                            const SizedBox(height: 20),
                            if (_register) ...[
                              SegmentedButton<String>(
                                segments: const [
                                  ButtonSegment(value: 'jobseeker', label: Text("I'm job hunting"), icon: Icon(Icons.person_search_rounded)),
                                  ButtonSegment(value: 'recruiter', label: Text("I'm hiring"), icon: Icon(Icons.groups_rounded)),
                                ],
                                selected: {_role},
                                onSelectionChanged: (s) => setState(() => _role = s.first),
                                showSelectedIcon: false,
                              ),
                              const SizedBox(height: 16),
                            ],
                            _GoogleButton(busy: _busy, onTap: _google),
                            const SizedBox(height: 18),
                            Row(children: [
                              Expanded(child: Divider(color: _edge)),
                              Padding(padding: const EdgeInsets.symmetric(horizontal: 12), child: Text('or with email', style: TextStyle(color: _sub, fontSize: 13))),
                              Expanded(child: Divider(color: _edge)),
                            ]),
                            const SizedBox(height: 18),
                            if (_register) ...[
                              TextField(controller: _name, style: const TextStyle(color: _txt), textCapitalization: TextCapitalization.words,
                                  textInputAction: TextInputAction.next, autofillHints: const [AutofillHints.name], decoration: _deco('Full name', Icons.person_outline_rounded)),
                              const SizedBox(height: 12),
                            ],
                            TextField(controller: _email, style: const TextStyle(color: _txt), keyboardType: TextInputType.emailAddress,
                                textInputAction: TextInputAction.next, autofillHints: const [AutofillHints.email], decoration: _deco('Email', Icons.mail_outline_rounded)),
                            const SizedBox(height: 12),
                            TextField(
                              controller: _pass,
                              style: const TextStyle(color: _txt),
                              obscureText: _hide,
                              textInputAction: TextInputAction.done,
                              onSubmitted: (_) => _submit(),
                              autofillHints: [_register ? AutofillHints.newPassword : AutofillHints.password],
                              decoration: _deco(_register ? 'Password (8+ characters)' : 'Password', Icons.lock_outline_rounded,
                                  suffix: IconButton(
                                    icon: Icon(_hide ? Icons.visibility_outlined : Icons.visibility_off_outlined, color: _sub),
                                    onPressed: () => setState(() => _hide = !_hide),
                                  )),
                            ),
                            if (_error != null) ...[
                              const SizedBox(height: 12),
                              Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                const Icon(Icons.error_outline_rounded, size: 18, color: Color(0xFFFF8A80)),
                                const SizedBox(width: 8),
                                Expanded(child: Text(_error!, style: const TextStyle(color: Color(0xFFFF8A80), fontSize: 13.5))),
                              ]),
                            ],
                            const SizedBox(height: 18),
                            SizedBox(
                              height: 52,
                              child: FilledButton(
                                onPressed: _busy ? null : _submit,
                                style: FilledButton.styleFrom(
                                  backgroundColor: Colors.white,
                                  foregroundColor: Colors.black,
                                  shape: const StadiumBorder(),
                                  textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                                ),
                                child: _busy
                                    ? const SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2.4, color: Colors.black))
                                    : Text(_register ? 'Create account' : 'Sign in'),
                              ),
                            ),
                            const SizedBox(height: 6),
                            TextButton(
                              onPressed: _busy ? null : () => setState(() {
                                _register = !_register;
                                _error = null;
                              }),
                              child: Text(_register ? 'Already have an account? Sign in' : 'New to Saige? Create account',
                                  style: const TextStyle(color: _txt, fontWeight: FontWeight.w600)),
                            ),
                          ]),
                        ),
                      ),
                    )),
                    const SizedBox(height: 16),
                    _fadeIn(2, Column(children: [
                      Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                        Icon(Icons.shield_outlined, size: 15, color: _sub),
                        const SizedBox(width: 6),
                        Text('Nothing is sent or applied without your approval', style: TextStyle(color: _sub, fontSize: 12.5)),
                      ]),
                      const SizedBox(height: 6),
                      Text('By continuing you agree to the Terms and Privacy Policy.', textAlign: TextAlign.center,
                          style: TextStyle(color: Colors.white.withValues(alpha: 0.45), fontSize: 11.5)),
                      const SizedBox(height: 4),
                      Text('Need help? info.saigeai@gmail.com', style: TextStyle(color: Colors.white.withValues(alpha: 0.45), fontSize: 11.5)),
                    ])),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _Chip extends StatelessWidget {
  const _Chip(this.icon, this.label);
  final IconData icon;
  final String label;
  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
        decoration: BoxDecoration(
          color: Colors.white.withValues(alpha: 0.08),
          borderRadius: BorderRadius.circular(99),
          border: Border.all(color: Colors.white.withValues(alpha: 0.14)),
        ),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          Icon(icon, size: 14, color: Colors.white),
          const SizedBox(width: 6),
          Text(label, style: const TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w500)),
        ]),
      );
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
            side: BorderSide.none,
            backgroundColor: Colors.white,
            foregroundColor: const Color(0xFF1F1F1F),
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
