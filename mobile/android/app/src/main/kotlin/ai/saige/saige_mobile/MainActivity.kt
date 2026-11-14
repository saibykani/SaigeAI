package ai.saige.saige_mobile

import android.content.Intent
import android.net.Uri
import android.os.Build
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import java.io.File

/**
 * Bridges launcher shortcuts, the home-screen widget and share intents to Dart over the "ai.saige/native" channel.
 * Cold start: Dart asks for "initial". Warm start (singleTop): we push "launch".
 */
class MainActivity : FlutterActivity() {
    private var channel: MethodChannel? = null
    private var pending: Map<String, Any?>? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        pending = parse(intent)
        val ch = MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "ai.saige/native")
        ch.setMethodCallHandler { call, result ->
            when (call.method) {
                "initial" -> {
                    result.success(pending)
                    pending = null
                }
                "updateWidget" -> {
                    @Suppress("UNCHECKED_CAST")
                    SaigeWidgetProvider.save(this, call.arguments as Map<String, Any?>)
                    result.success(null)
                }
                else -> result.notImplemented()
            }
        }
        channel = ch
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        val p = parse(intent)
        if (p != null) channel?.invokeMethod("launch", p)
    }

    private fun parse(i: Intent?): Map<String, Any?>? {
        if (i == null) return null
        val out: Map<String, Any?>? = when (i.action) {
            ROUTE -> mapOf(
                "kind" to "route",
                "route" to (i.getStringExtra("route") ?: "home"),
                "mic" to (i.getBooleanExtra("mic", false) || i.getStringExtra("mic") == "true"),
                "id" to i.getStringExtra("id"),
            )
            Intent.ACTION_SEND -> {
                val type = i.type ?: ""
                if (type.startsWith("image/")) {
                    val uri = streamUri(i)
                    val path = uri?.let { copyToCache(it) }
                    if (path != null) mapOf("kind" to "share", "image" to path) else null
                } else {
                    val text = i.getStringExtra(Intent.EXTRA_TEXT)
                    if (text.isNullOrBlank()) null else mapOf("kind" to "share", "text" to text, "subject" to i.getStringExtra(Intent.EXTRA_SUBJECT))
                }
            }
            else -> null
        }
        if (out != null) i.action = Intent.ACTION_MAIN // do not replay on recreation
        return out
    }

    private fun streamUri(i: Intent): Uri? =
        if (Build.VERSION.SDK_INT >= 33) i.getParcelableExtra(Intent.EXTRA_STREAM, Uri::class.java)
        else @Suppress("DEPRECATION") i.getParcelableExtra(Intent.EXTRA_STREAM)

    private fun copyToCache(uri: Uri): String? = try {
        val f = File(cacheDir, "shared_${System.currentTimeMillis()}.img")
        contentResolver.openInputStream(uri)?.use { input -> f.outputStream().use { input.copyTo(it) } }
        if (f.length() > 0) f.absolutePath else null
    } catch (_: Exception) {
        null
    }

    companion object {
        const val ROUTE = "ai.saige.ROUTE"
    }
}
