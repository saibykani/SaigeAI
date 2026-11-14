package ai.saige.saige_mobile

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.view.View
import android.widget.RemoteViews

/** Home-screen widget: next interview + new matches. Data is written from Dart (SharedPreferences "saige_widget"). */
class SaigeWidgetProvider : AppWidgetProvider() {
    override fun onUpdate(context: Context, manager: AppWidgetManager, ids: IntArray) {
        for (id in ids) manager.updateAppWidget(id, build(context))
    }

    companion object {
        private const val PREFS = "saige_widget"

        fun save(context: Context, data: Map<String, Any?>) {
            val e = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            e.putString("interview", data["interview"] as? String ?: "")
            e.putString("interviewId", data["interviewId"] as? String ?: "")
            e.putString("matches", data["matches"] as? String ?: "")
            e.apply()
            val mgr = AppWidgetManager.getInstance(context)
            val ids = mgr.getAppWidgetIds(ComponentName(context, SaigeWidgetProvider::class.java))
            for (id in ids) mgr.updateAppWidget(id, build(context))
        }

        private fun pi(context: Context, code: Int, route: String, id: String?): PendingIntent {
            val i = Intent(context, MainActivity::class.java).setAction(MainActivity.ROUTE).putExtra("route", route)
            if (id != null) i.putExtra("id", id)
            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP)
            return PendingIntent.getActivity(context, code, i, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        }

        fun build(context: Context): RemoteViews {
            val p = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            val interview = p.getString("interview", "") ?: ""
            val interviewId = p.getString("interviewId", "") ?: ""
            val matches = p.getString("matches", "") ?: ""
            val v = RemoteViews(context.packageName, R.layout.saige_widget)
            v.setTextViewText(R.id.w_interview, if (interview.isEmpty()) "No interviews scheduled" else interview)
            v.setTextViewText(R.id.w_matches, if (matches.isEmpty()) "Open Saige to refresh" else matches)
            v.setOnClickPendingIntent(R.id.w_root, pi(context, 1, "home", null))
            if (interviewId.isNotEmpty()) {
                v.setOnClickPendingIntent(R.id.w_interview_box, pi(context, 2, "interview", interviewId))
                v.setViewVisibility(R.id.w_prep, View.VISIBLE)
            } else {
                v.setOnClickPendingIntent(R.id.w_interview_box, pi(context, 1, "home", null))
                v.setViewVisibility(R.id.w_prep, View.GONE)
            }
            return v
        }
    }
}
