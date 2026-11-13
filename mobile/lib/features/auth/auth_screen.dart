import 'dart:ui' as ui;

import 'package:material_ui/material_ui.dart';

import '../../core/api.dart';
import '../../core/google_auth.dart';
import '../../core/motion.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/dot_ring.dart';
import '../../core/widgets/galaxy.dart';
import '../../core/widgets/logo.dart';

/// Sign in / create account. The Milky Way fills the top with a slow camera drift, the wordmark blurs in
/// letter by letter, and a clean sheet springs up from the bottom with Google-style floating-label fields.
class AuthScreen extends StatefulWidget {
  const AuthScreen({super.key});
  @override
  State<AuthScreen> createState() => _AuthScreenState();
}

class _AuthScreenState extends State<AuthScreen> with TickerProviderStateMixin {
  final _name = TextEditingController();
  final _email = TextEditingController();
  final _pass = TextEditingController();
  bool _register = false;
  bool _busy = false;
  bool _hide = true;
  String _role = 'jobseeker';
  String? _error;

  late final AnimationController _intro = AnimationController(vsync: this, duration: const Duration(milliseconds: 3400))..forward();
  late final AnimationController _drift = AnimationController(vsync: this, duration: const Duration(seconds: 36))..repeat(reverse: true);

  @override
  void dispose() {
    _name.dispose();
    _email.dispose();
    _pass.dispose();
    _intro.dispose();
    _drift.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    FocusScope.of(context).unfocus();
    final email = _email.text.trim();
    if (!email.contains('@') || _pass.text.isEmpty || (_register && (_name.text.trim().isEmpty || _pass.text.length < 8))) {
      _fail(_register ? 'Add your name, a valid email and a password of 8+ characters.' : 'Enter your email and password to continue.');
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
      success();
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

  void _mode(bool register) {
    if (register == _register) return;
    tick();
    setState(() {
      _register = register;
      _error = null;
    });
  }

  @override
  Widget build(BuildContext context) {
    final kb = MediaQuery.viewInsetsOf(context).bottom > 0;
    return Scaffold(
      backgroundColor: C.bg,
      resizeToAvoidBottomInset: true,
      body: LayoutBuilder(builder: (context, box) => Column(children: [
        // Galaxy hero: rounded bottom edge, slow zoom drift, wordmark blurs in letter by letter.
        Expanded(
          child: ClipRRect(
            borderRadius: const BorderRadius.vertical(bottom: Radius.circular(40)),
            child: ColoredBox(
              color: Colors.black,
              child: AnimatedBuilder(
                animation: _drift,
                child: GalaxyBackground(child: _Hero(intro: _intro, compact: kb)),
                builder: (context, child) {
                  final t = Curves.easeInOut.transform(_drift.value);
                  return Transform.scale(scale: 1.04 + 0.1 * t, child: Transform.translate(offset: Offset(-14 * t, 8 * t), child: child));
                },
              ),
            ),
          ),
        ),
        // Sheet rises with a spring after the wordmark lands.
        _Rise(
          intro: _intro,
          child: Container(
            width: double.infinity,
            color: C.bg,
            child: SafeArea(
              top: false,
              child: SingleChildScrollView(
                padding: const EdgeInsets.fromLTRB(24, 22, 24, 14),
                child: ConstrainedBox(
                  constraints: BoxConstraints(maxHeight: box.maxHeight * 0.8),
                  child: _form(),
                ),
              ),
            ),
          ),
        ),
      ])),
    );
  }

  Widget _form() => AnimatedSize(
        duration: const Duration(milliseconds: 420),
        curve: softSpring,
        alignment: Alignment.topCenter,
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          _Segmented(register: _register, onChanged: _mode),
          const SizedBox(height: 18),
          if (_register) ...[
            Row(children: [
              Expanded(child: _RoleCard(label: 'Job seeker', icon: Icons.person_search_rounded, on: _role == 'jobseeker', onTap: () => setState(() => _role = 'jobseeker'))),
              const SizedBox(width: 10),
              Expanded(child: _RoleCard(label: 'Recruiter', icon: Icons.groups_rounded, on: _role == 'recruiter', onTap: () => setState(() => _role = 'recruiter'))),
            ]),
            const SizedBox(height: 14),
          ],
          _GoogleButton(busy: _busy, onTap: _google),
          const SizedBox(height: 16),
          Row(children: [
            Expanded(child: Divider(color: C.line, height: 1)),
            Padding(padding: const EdgeInsets.symmetric(horizontal: 14), child: Text('or', style: T.small)),
            Expanded(child: Divider(color: C.line, height: 1)),
          ]),
          const SizedBox(height: 16),
          if (_register) ...[
            _Field(controller: _name, label: 'Full name', icon: Icons.person_outline_rounded, capitalize: true),
            const SizedBox(height: 12),
          ],
          _Field(controller: _email, label: 'Email', icon: Icons.mail_outline_rounded, keyboard: TextInputType.emailAddress, hints: const [AutofillHints.email]),
          const SizedBox(height: 12),
          _Field(
            controller: _pass,
            label: 'Password',
            icon: Icons.lock_outline_rounded,
            obscure: _hide,
            onSubmit: _submit,
            suffix: Pressable(
              scale: 0.85,
              onTap: () => setState(() => _hide = !_hide),
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: AnimatedSwitcher(
                  duration: const Duration(milliseconds: 260),
                  transitionBuilder: (c, a) => RotationTransition(turns: Tween(begin: 0.75, end: 1.0).animate(a), child: ScaleTransition(scale: a, child: FadeTransition(opacity: a, child: c))),
                  child: Icon(_hide ? Icons.visibility_off_outlined : Icons.visibility_outlined, key: ValueKey(_hide), color: C.muted, size: 22),
                ),
              ),
            ),
          ),
          AnimatedSwitcher(
            duration: const Duration(milliseconds: 300),
            transitionBuilder: (c, a) => SizeTransition(sizeFactor: a, alignment: Alignment.topCenter, child: FadeTransition(opacity: a, child: c)),
            child: _error == null
                ? const SizedBox(key: ValueKey('none'), width: double.infinity)
                : Padding(
                    key: ValueKey(_error),
                    padding: const EdgeInsets.only(top: 14),
                    child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Icon(Icons.info_outline_rounded, size: 18, color: C.bad),
                      const SizedBox(width: 8),
                      Expanded(child: Text(_error!, style: TextStyle(color: C.bad, fontSize: 13.5, height: 1.3))),
                    ]),
                  ),
          ),
          const SizedBox(height: 20),
          _ShimmerButton(label: _register ? 'Create account' : 'Sign in', busy: _busy, onTap: _submit),
          const SizedBox(height: 14),
          Text('Nothing is sent or applied without your approval.', style: T.small, textAlign: TextAlign.center),
        ]),
      );
}

/// Galaxy overlay: logo mark scales in, then each letter of the wordmark blurs and rises into place.
class _Hero extends StatelessWidget {
  const _Hero({required this.intro, required this.compact});
  final AnimationController intro;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    const word = 'Saige AI';
    return SafeArea(
      child: IgnorePointer(
        child: Center(
          child: AnimatedBuilder(
            animation: intro,
            builder: (context, _) {
              final t = intro.value;
              double seg(double a, double b, [Curve c = Curves.easeOutCubic]) => c.transform(((t - a) / (b - a)).clamp(0.0, 1.0));
              final mark = seg(0.0, 0.3);
              return FittedBox(
                fit: BoxFit.scaleDown,
                child: Column(mainAxisSize: MainAxisSize.min, children: [
                  Opacity(opacity: mark, child: Transform.scale(scale: 0.7 + 0.3 * softSpring.transform(mark), child: LogoMark(size: compact ? 44 : 72, radius: 0.26))),
                  SizedBox(height: compact ? 10 : 20),
                  Row(mainAxisSize: MainAxisSize.min, children: [
                    for (var i = 0; i < word.length; i++)
                      () {
                        final p = seg(0.18 + i * 0.045, 0.38 + i * 0.045);
                        return Opacity(
                          opacity: p,
                          child: Transform.translate(
                            offset: Offset(0, 14 * (1 - p)),
                            child: ImageFiltered(
                              enabled: p < 1,
                              imageFilter: ui.ImageFilter.blur(sigmaX: 8 * (1 - p), sigmaY: 8 * (1 - p)),
                              child: Text(word[i] == ' ' ? ' ' : word[i], style: const TextStyle(fontSize: 44, fontWeight: FontWeight.w700, letterSpacing: -1.5, color: Colors.white, height: 1.1)),
                            ),
                          ),
                        );
                      }(),
                  ]),
                  if (!compact) ...[
                    const SizedBox(height: 10),
                    Opacity(opacity: seg(0.62, 0.85), child: Transform.translate(offset: Offset(0, 8 * (1 - seg(0.62, 0.85))), child: const Text('Your career copilot. Truthful by design.', style: TextStyle(color: Color(0xCCFFFFFF), fontSize: 14.5, letterSpacing: 0.1)))),
                  ],
                ]),
              );
            },
          ),
        ),
      ),
    );
  }
}

/// Slides the sheet up with a spring once the intro reaches the wordmark.
class _Rise extends StatelessWidget {
  const _Rise({required this.intro, required this.child});
  final AnimationController intro;
  final Widget child;
  @override
  Widget build(BuildContext context) => AnimatedBuilder(
        animation: intro,
        child: child,
        builder: (context, child) {
          final p = ((intro.value - 0.12) / 0.4).clamp(0.0, 1.0);
          final s = softSpring.transform(p);
          return Opacity(opacity: Curves.easeOut.transform(p), child: Transform.translate(offset: Offset(0, 140 * (1 - s)), child: child));
        },
      );
}

/// Google-style filled field: floating label, animated focus underline glow.
class _Field extends StatefulWidget {
  const _Field({required this.controller, required this.label, required this.icon, this.obscure = false, this.suffix, this.keyboard, this.hints, this.onSubmit, this.capitalize = false});
  final TextEditingController controller;
  final String label;
  final IconData icon;
  final bool obscure;
  final Widget? suffix;
  final TextInputType? keyboard;
  final List<String>? hints;
  final VoidCallback? onSubmit;
  final bool capitalize;
  @override
  State<_Field> createState() => _FieldState();
}

class _FieldState extends State<_Field> {
  final _focus = FocusNode();
  @override
  void initState() {
    super.initState();
    _focus.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _focus.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final on = _focus.hasFocus;
    return AnimatedContainer(
      duration: const Duration(milliseconds: 240),
      curve: Curves.easeOutCubic,
      decoration: BoxDecoration(
        color: on ? C.surface : C.surface2,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: on ? C.primary : Colors.transparent, width: 1.6),
        boxShadow: on ? [BoxShadow(color: C.primary.withValues(alpha: 0.28), blurRadius: 16, spreadRadius: 0.5)] : const [],
      ),
      child: TextField(
        controller: widget.controller,
        focusNode: _focus,
        obscureText: widget.obscure,
        keyboardType: widget.keyboard,
        autofillHints: widget.hints,
        textCapitalization: widget.capitalize ? TextCapitalization.words : TextCapitalization.none,
        textInputAction: widget.onSubmit != null ? TextInputAction.done : TextInputAction.next,
        onSubmitted: widget.onSubmit == null ? null : (_) => widget.onSubmit!(),
        style: TextStyle(color: C.text, fontSize: 16),
        cursorColor: C.primary,
        decoration: InputDecoration(
          labelText: widget.label,
          labelStyle: TextStyle(color: on ? C.primary : C.muted),
          floatingLabelStyle: TextStyle(color: C.primary, fontWeight: FontWeight.w600),
          prefixIcon: Icon(widget.icon, color: on ? C.primary : C.muted, size: 22),
          suffixIcon: widget.suffix,
          filled: false,
          border: InputBorder.none,
          enabledBorder: InputBorder.none,
          focusedBorder: InputBorder.none,
          contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 18),
        ),
      ),
    );
  }
}

class _Segmented extends StatelessWidget {
  const _Segmented({required this.register, required this.onChanged});
  final bool register;
  final ValueChanged<bool> onChanged;
  @override
  Widget build(BuildContext context) => Container(
        height: 48,
        padding: const EdgeInsets.all(4),
        decoration: BoxDecoration(color: C.surface2, borderRadius: BorderRadius.circular(99)),
        child: Stack(children: [
          AnimatedAlign(
            duration: const Duration(milliseconds: 450),
            curve: springy,
            alignment: register ? Alignment.centerRight : Alignment.centerLeft,
            child: FractionallySizedBox(
              widthFactor: 0.5,
              child: Container(decoration: BoxDecoration(color: C.surface, borderRadius: BorderRadius.circular(99), boxShadow: C.shadow, border: C.dark ? Border.all(color: C.line) : null)),
            ),
          ),
          Row(children: [
            for (final (i, l) in ['Sign in', 'Create account'].indexed)
              Expanded(
                child: Pressable(
                  haptic: false,
                  scale: 0.97,
                  onTap: () => onChanged(i == 1),
                  child: Center(child: AnimatedDefaultTextStyle(duration: const Duration(milliseconds: 250), style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14.5, color: register == (i == 1) ? C.text : C.muted), child: Text(l))),
                ),
              ),
          ]),
        ]),
      );
}

class _RoleCard extends StatelessWidget {
  const _RoleCard({required this.label, required this.icon, required this.on, required this.onTap});
  final String label;
  final IconData icon;
  final bool on;
  final VoidCallback onTap;
  @override
  Widget build(BuildContext context) => Pressable(
        onTap: onTap,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 280),
          curve: Curves.easeOutCubic,
          height: 52,
          decoration: BoxDecoration(
            color: on ? C.primarySoft : C.surface2,
            borderRadius: BorderRadius.circular(99),
            border: Border.all(color: on ? C.primary : Colors.transparent, width: 1.6),
          ),
          child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
            AnimatedSwitcher(duration: const Duration(milliseconds: 250), transitionBuilder: (c, a) => ScaleTransition(scale: a, child: c), child: Icon(on ? Icons.check_circle_rounded : icon, key: ValueKey(on), size: 20, color: on ? C.primary : C.muted)),
            const SizedBox(width: 8),
            Text(label, style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: on ? C.text : C.muted)),
          ]),
        ),
      );
}

/// Pill button with a slow shimmer sweep, press depth, and a DotRing while busy.
class _ShimmerButton extends StatefulWidget {
  const _ShimmerButton({required this.label, required this.busy, required this.onTap});
  final String label;
  final bool busy;
  final VoidCallback onTap;
  @override
  State<_ShimmerButton> createState() => _ShimmerButtonState();
}

class _ShimmerButtonState extends State<_ShimmerButton> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 2800))..repeat();

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Pressable(
        onTap: widget.busy ? null : widget.onTap,
        scale: 0.96,
        child: Container(
          height: 56,
          decoration: BoxDecoration(borderRadius: BorderRadius.circular(99), color: C.primary, boxShadow: [BoxShadow(color: C.primary.withValues(alpha: 0.35), blurRadius: 22, offset: const Offset(0, 8))]),
          clipBehavior: Clip.antiAlias,
          child: Stack(alignment: Alignment.center, children: [
            if (!widget.busy)
              Positioned.fill(
                child: AnimatedBuilder(
                  animation: _c,
                  builder: (context, _) {
                    final x = -1.5 + 4 * Curves.easeInOut.transform(_c.value);
                    return DecoratedBox(
                      decoration: BoxDecoration(gradient: LinearGradient(begin: Alignment(x - 0.5, -0.3), end: Alignment(x + 0.5, 0.3), colors: [C.onPrimary.withValues(alpha: 0), C.onPrimary.withValues(alpha: 0.22), C.onPrimary.withValues(alpha: 0)])),
                    );
                  },
                ),
              ),
            AnimatedSwitcher(
              duration: const Duration(milliseconds: 250),
              child: widget.busy ? DotRing(key: const ValueKey('b'), size: 26, dots: 12, color: C.onPrimary) : Text(widget.label, key: const ValueKey('t'), style: TextStyle(color: C.onPrimary, fontWeight: FontWeight.w700, fontSize: 16.5, letterSpacing: -0.2)),
            ),
          ]),
        ),
      );
}

/// "Continue with Google": white pill, thin border, multicolour G (Google branding guidelines).
/// Stays white in dark themes as Google allows (light variant with a neutral border).
class _GoogleButton extends StatelessWidget {
  const _GoogleButton({required this.busy, required this.onTap});
  final bool busy;
  final VoidCallback onTap;
  @override
  Widget build(BuildContext context) => Pressable(
        onTap: busy ? null : onTap,
        scale: 0.97,
        child: Container(
          height: 52,
          decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(99), border: Border.all(color: const Color(0xFF747775))),
          child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
            const SizedBox(width: 20, height: 20, child: CustomPaint(painter: _GoogleG())),
            const SizedBox(width: 12),
            const Text('Continue with Google', style: TextStyle(color: Color(0xFF1F1F1F), fontSize: 15.5, fontWeight: FontWeight.w600, letterSpacing: 0.1)),
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
    // Angles run clockwise from 3 o'clock; the gap between -45 degrees and 0 is the G's opening.
    canvas.drawArc(rect, -pi * 0.75, pi * 0.5, false, p(const Color(0xFFEA4335))); // top
    canvas.drawArc(rect, pi * 0.75, pi * 0.5, false, p(const Color(0xFFFBBC05))); // left
    canvas.drawArc(rect, pi * 0.25, pi * 0.5, false, p(const Color(0xFF34A853))); // bottom
    // Blue crossbar and right-hand tail.
    final blue = Paint()..color = const Color(0xFF4285F4);
    canvas.drawRect(Rect.fromLTRB(s * 0.5, s * 0.4, s * 0.98, s * 0.6), blue);
    canvas.drawArc(rect, 0, pi * 0.25, false, p(const Color(0xFF4285F4)));
  }

  @override
  bool shouldRepaint(covariant CustomPainter old) => false;
}
