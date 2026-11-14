import 'dart:math' as math;
import 'dart:ui' as ui;

import 'package:material_ui/material_ui.dart';

import '../../core/api.dart';
import '../../core/google_auth.dart';
import '../../core/motion.dart';
import '../../core/session.dart';
import '../../core/widgets/confetti.dart';
import 'login_stage.dart';

const _paper = Color(0xFFECEBE7);
const _ink = Color(0xFF0A0B10);
const _glow = Color(0xFF4C8DF6);
const _bad = Color(0xFFFF8A80);

/// Sign in / create account over the living aurora stage. The form is one frosted-glass card that springs up
/// after the logo has assembled itself. All auth logic (login, register, role, Google) is unchanged.
class AuthScreen extends StatefulWidget {
  const AuthScreen({super.key});
  @override
  State<AuthScreen> createState() => _AuthScreenState();
}

class _AuthScreenState extends State<AuthScreen> with TickerProviderStateMixin {
  final _name = TextEditingController();
  final _email = TextEditingController();
  final _pass = TextEditingController();
  final _btnKey = GlobalKey();
  bool _register = false;
  bool _busy = false;
  bool _done = false;
  bool _hide = true;
  String _role = 'jobseeker';
  String? _error;

  late final AnimationController _rise = AnimationController(vsync: this, duration: const Duration(milliseconds: 1500));
  late final AnimationController _shake = AnimationController(vsync: this, duration: const Duration(milliseconds: 520));
  bool _started = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_started) return;
    _started = true;
    if (MediaQuery.disableAnimationsOf(context)) {
      _rise.value = 1;
    } else {
      Future<void>.delayed(const Duration(milliseconds: 1500), () {
        if (mounted) _rise.forward();
      });
    }
  }

  @override
  void dispose() {
    _name.dispose();
    _email.dispose();
    _pass.dispose();
    _rise.dispose();
    _shake.dispose();
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
      _success();
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
      _success();
    } on ApiException catch (e) {
      _fail(e.message);
    } catch (_) {
      _fail('Google sign-in did not work. Check your connection and try again.');
    }
  }

  /// The session is already live here (the root cross-fades to the app); morph the button to a check and burst confetti.
  void _success() {
    if (!mounted) return;
    setState(() {
      _busy = false;
      _done = true;
    });
    Offset? origin;
    final box = _btnKey.currentContext?.findRenderObject();
    if (box is RenderBox && box.attached) origin = box.localToGlobal(box.size.center(Offset.zero));
    Confetti.burst(context, origin: origin);
  }

  void _fail(String m) {
    tap();
    if (mounted) {
      setState(() {
        _error = m;
        _busy = false;
      });
      _shake.forward(from: 0);
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
      backgroundColor: _ink,
      resizeToAvoidBottomInset: false,
      body: LoginStage(compact: kb, child: _card()),
    );
  }

  Widget _card() => AnimatedBuilder(
        animation: Listenable.merge([_rise, _shake]),
        builder: (context, child) {
          final r = softSpring.transform(_rise.value.clamp(0.0, 1.0));
          final dx = math.sin(_shake.value * math.pi * 6) * (1 - _shake.value) * 9;
          return Opacity(
            opacity: Curves.easeOut.transform((_rise.value * 2).clamp(0.0, 1.0)),
            child: Transform.translate(offset: Offset(dx, (1 - r) * 420), child: child),
          );
        },
        child: Padding(
          padding: const EdgeInsets.fromLTRB(14, 0, 14, 14),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(32),
            child: BackdropFilter(
              filter: ui.ImageFilter.blur(sigmaX: 22, sigmaY: 22),
              child: Container(
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.10),
                  borderRadius: BorderRadius.circular(32),
                  border: Border.all(color: Colors.white.withValues(alpha: 0.22)),
                ),
                child: SingleChildScrollView(
                  padding: const EdgeInsets.fromLTRB(20, 20, 20, 18),
                  child: _form(),
                ),
              ),
            ),
          ),
        ),
      );

  Widget _form() => AnimatedSize(
        duration: const Duration(milliseconds: 420),
        curve: softSpring,
        alignment: Alignment.topCenter,
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          _Segmented(register: _register, onChanged: _mode),
          const SizedBox(height: 16),
          if (_register) ...[
            Row(children: [
              Expanded(child: _RoleCard(label: 'Job seeker', icon: Icons.person_search_rounded, on: _role == 'jobseeker', onTap: () => setState(() => _role = 'jobseeker'))),
              const SizedBox(width: 10),
              Expanded(child: _RoleCard(label: 'Recruiter', icon: Icons.groups_rounded, on: _role == 'recruiter', onTap: () => setState(() => _role = 'recruiter'))),
            ]),
            const SizedBox(height: 14),
          ],
          _GoogleButton(busy: _busy || _done, onTap: _google),
          const SizedBox(height: 14),
          Row(children: [
            Expanded(child: Divider(color: Colors.white.withValues(alpha: 0.2), height: 1)),
            Padding(padding: const EdgeInsets.symmetric(horizontal: 14), child: Text('or with email', style: TextStyle(color: Colors.white.withValues(alpha: 0.6), fontSize: 12.5))),
            Expanded(child: Divider(color: Colors.white.withValues(alpha: 0.2), height: 1)),
          ]),
          const SizedBox(height: 14),
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
                  duration: const Duration(milliseconds: 280),
                  transitionBuilder: (c, a) => RotationTransition(turns: Tween(begin: 0.75, end: 1.0).animate(a), child: ScaleTransition(scale: a, child: FadeTransition(opacity: a, child: c))),
                  child: Icon(_hide ? Icons.visibility_off_outlined : Icons.visibility_outlined, key: ValueKey(_hide), color: Colors.white70, size: 22),
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
                    padding: const EdgeInsets.only(top: 12),
                    child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      const Icon(Icons.info_outline_rounded, size: 18, color: _bad),
                      const SizedBox(width: 8),
                      Expanded(child: Text(_error!, style: const TextStyle(color: _bad, fontSize: 13.5, height: 1.3))),
                    ]),
                  ),
          ),
          const SizedBox(height: 18),
          _ShimmerButton(key: _btnKey, label: _register ? 'Create account' : 'Sign in', busy: _busy, done: _done, onTap: _submit),
          const SizedBox(height: 12),
          Text('Nothing is sent or applied without your approval.', style: TextStyle(color: Colors.white.withValues(alpha: 0.55), fontSize: 12.5), textAlign: TextAlign.center),
        ]),
      );
}

/// Floating-label field with a glowing focus ring.
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
    OutlineInputBorder b(Color c, double w) => OutlineInputBorder(borderRadius: BorderRadius.circular(18), borderSide: BorderSide(color: c, width: w));
    return AnimatedContainer(
      duration: const Duration(milliseconds: 260),
      curve: Curves.easeOutCubic,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(18),
        boxShadow: on ? [BoxShadow(color: _glow.withValues(alpha: 0.5), blurRadius: 20, spreadRadius: 1)] : const [],
      ),
      child: TextField(
        controller: widget.controller,
        focusNode: _focus,
        obscureText: widget.obscure,
        keyboardType: widget.keyboard,
        autofillHints: widget.hints,
        textCapitalization: widget.capitalize ? TextCapitalization.words : TextCapitalization.none,
        textInputAction: widget.onSubmit == null ? TextInputAction.next : TextInputAction.done,
        onSubmitted: (_) => widget.onSubmit?.call(),
        cursorColor: Colors.white,
        style: const TextStyle(color: Colors.white, fontSize: 16),
        decoration: InputDecoration(
          labelText: widget.label,
          labelStyle: TextStyle(color: Colors.white.withValues(alpha: 0.65)),
          floatingLabelStyle: TextStyle(color: on ? Colors.white : Colors.white70, fontWeight: FontWeight.w600),
          filled: true,
          fillColor: Colors.white.withValues(alpha: on ? 0.16 : 0.09),
          prefixIcon: Icon(widget.icon, color: on ? Colors.white : Colors.white60, size: 21),
          suffixIcon: widget.suffix,
          contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 17),
          border: b(Colors.white.withValues(alpha: 0.14), 1),
          enabledBorder: b(Colors.white.withValues(alpha: 0.14), 1),
          focusedBorder: b(Colors.white.withValues(alpha: 0.85), 1.5),
        ),
      ),
    );
  }
}

/// Sign in / Create account with a sliding thumb.
class _Segmented extends StatelessWidget {
  const _Segmented({required this.register, required this.onChanged});
  final bool register;
  final ValueChanged<bool> onChanged;
  @override
  Widget build(BuildContext context) => Container(
        height: 46,
        padding: const EdgeInsets.all(4),
        decoration: BoxDecoration(color: Colors.black.withValues(alpha: 0.28), borderRadius: BorderRadius.circular(99)),
        child: Stack(children: [
          AnimatedAlign(
            duration: const Duration(milliseconds: 460),
            curve: softSpring,
            alignment: register ? Alignment.centerRight : Alignment.centerLeft,
            child: FractionallySizedBox(widthFactor: 0.5, heightFactor: 1, child: DecoratedBox(decoration: BoxDecoration(color: _paper, borderRadius: BorderRadius.circular(99)))),
          ),
          Row(children: [
            for (final (label, reg) in const [('Sign in', false), ('Create account', true)])
              Expanded(
                child: GestureDetector(
                  behavior: HitTestBehavior.opaque,
                  onTap: () => onChanged(reg),
                  child: Center(
                    child: AnimatedDefaultTextStyle(
                      duration: const Duration(milliseconds: 240),
                      style: TextStyle(fontWeight: FontWeight.w700, fontSize: 14, color: register == reg ? _ink : Colors.white.withValues(alpha: 0.75)),
                      child: Text(label),
                    ),
                  ),
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
        scale: 0.95,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 280),
          curve: Curves.easeOutCubic,
          padding: const EdgeInsets.symmetric(vertical: 13),
          decoration: BoxDecoration(
            color: on ? Colors.white.withValues(alpha: 0.2) : Colors.white.withValues(alpha: 0.06),
            borderRadius: BorderRadius.circular(18),
            border: Border.all(color: on ? Colors.white.withValues(alpha: 0.9) : Colors.white.withValues(alpha: 0.14), width: on ? 1.5 : 1),
            boxShadow: on ? [BoxShadow(color: _glow.withValues(alpha: 0.35), blurRadius: 16)] : const [],
          ),
          child: Column(children: [
            TweenAnimationBuilder<double>(
              tween: Tween(begin: 0, end: on ? 1 : 0),
              duration: const Duration(milliseconds: 520),
              curve: springy,
              builder: (_, v, child) => Transform.rotate(angle: 0.2 * math.sin(v * math.pi), child: Transform.scale(scale: 1 + 0.22 * v.clamp(0.0, 1.4), child: child)),
              child: Icon(icon, color: on ? Colors.white : Colors.white60, size: 24),
            ),
            const SizedBox(height: 6),
            Text(label, style: TextStyle(fontSize: 13.5, fontWeight: FontWeight.w700, color: on ? Colors.white : Colors.white70)),
          ]),
        ),
      );
}

/// Paper pill with a travelling sheen. While busy it shows a spinner; on success it morphs to a check circle.
class _ShimmerButton extends StatefulWidget {
  const _ShimmerButton({super.key, required this.label, required this.busy, required this.done, required this.onTap});
  final String label;
  final bool busy;
  final bool done;
  final VoidCallback onTap;
  @override
  State<_ShimmerButton> createState() => _ShimmerButtonState();
}

class _ShimmerButtonState extends State<_ShimmerButton> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 2600));
  bool _on = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final reduced = MediaQuery.disableAnimationsOf(context);
    if (!reduced && !_on) {
      _on = true;
      _c.repeat();
    } else if (reduced && _on) {
      _on = false;
      _c.stop();
    }
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => LayoutBuilder(builder: (context, box) {
        final w = widget.done ? 56.0 : box.maxWidth;
        return Align(
          child: Pressable(
            onTap: (widget.busy || widget.done) ? null : widget.onTap,
            scale: 0.95,
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 520),
              curve: softSpring,
              width: w,
              height: 56,
              decoration: BoxDecoration(
                color: widget.done ? const Color(0xFF34A853) : _paper,
                borderRadius: BorderRadius.circular(99),
                boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.35), blurRadius: 18, offset: const Offset(0, 8))],
              ),
              clipBehavior: Clip.antiAlias,
              child: Stack(alignment: Alignment.center, children: [
                if (!widget.done && !widget.busy)
                  AnimatedBuilder(
                    animation: _c,
                    builder: (context, _) {
                      final x = -0.6 + 2.2 * Curves.easeInOut.transform(_c.value);
                      return FractionalTranslation(
                        translation: Offset(x, 0),
                        child: Transform(
                          transform: Matrix4.skewX(-0.35),
                          child: FractionallySizedBox(
                            widthFactor: 0.35,
                            child: DecoratedBox(
                              decoration: BoxDecoration(gradient: LinearGradient(colors: [Colors.white.withValues(alpha: 0), _glow.withValues(alpha: 0.28), Colors.white.withValues(alpha: 0)])),
                              child: const SizedBox.expand(),
                            ),
                          ),
                        ),
                      );
                    },
                  ),
                AnimatedSwitcher(
                  duration: const Duration(milliseconds: 320),
                  transitionBuilder: (c, a) => ScaleTransition(scale: a, child: FadeTransition(opacity: a, child: c)),
                  child: widget.done
                      ? const Icon(Icons.check_rounded, key: ValueKey('done'), color: Colors.white, size: 30)
                      : widget.busy
                          ? const SizedBox(key: ValueKey('busy'), width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2.6, color: _ink))
                          : Text(widget.label, key: const ValueKey('label'), style: const TextStyle(color: _ink, fontSize: 16.5, fontWeight: FontWeight.w700, letterSpacing: 0.1)),
                ),
              ]),
            ),
          ),
        );
      });
}

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
          decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(99), boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.25), blurRadius: 14, offset: const Offset(0, 6))]),
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
