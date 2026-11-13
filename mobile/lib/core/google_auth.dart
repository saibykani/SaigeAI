import 'package:google_sign_in/google_sign_in.dart';

/// Native Google sign-in. Returns a Google ID token whose audience is the WEB OAuth client id, which the
/// API verifies at POST /auth/google/mobile. Returns null when the user cancels.
class GoogleAuth {
  /// The *Web application* OAuth client id from Google Cloud (same one as the API's GOOGLE_CLIENT_ID).
  /// Pass it at build time: --dart-define=GOOGLE_WEB_CLIENT_ID=xxxx.apps.googleusercontent.com
  // TODO: the web client id is not in the repo; set it via dart-define or paste it here.
  static const webClientId = String.fromEnvironment('GOOGLE_WEB_CLIENT_ID');

  static bool get configured => webClientId.isNotEmpty;
  static bool _ready = false;

  static Future<String?> idToken() async {
    final g = GoogleSignIn.instance;
    if (!_ready) {
      await g.initialize(serverClientId: webClientId);
      _ready = true;
    }
    try {
      final account = await g.authenticate();
      return account.authentication.idToken;
    } on GoogleSignInException catch (e) {
      if (e.code == GoogleSignInExceptionCode.canceled) return null;
      rethrow;
    }
  }
}
