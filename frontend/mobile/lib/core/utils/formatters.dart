import 'package:intl/intl.dart';

/// Date and text helpers.
///
/// The backend stores ISO-8601 UTC, so everything is converted to local time
/// before display - otherwise a complaint filed at 9pm IST shows yesterday's
/// date.
class Format {
  const Format._();

  /// "2 hours ago", "3 days ago", or a date once it is older than a week.
  static String relative(DateTime? value) {
    if (value == null) return '-';
    final local = value.toLocal();
    final diff = DateTime.now().difference(local);

    if (diff.isNegative) return dayMonth(local); // scheduled in the future
    if (diff.inMinutes < 1) return 'Just now';
    if (diff.inMinutes < 60) {
      return '${diff.inMinutes} min ago';
    }
    if (diff.inHours < 24) {
      return diff.inHours == 1 ? '1 hour ago' : '${diff.inHours} hours ago';
    }
    if (diff.inDays == 1) return 'Yesterday';
    if (diff.inDays < 7) return '${diff.inDays} days ago';
    return dayMonth(local);
  }

  /// "12 Aug 2026"
  static String dayMonth(DateTime? value) =>
      value == null ? '-' : DateFormat('d MMM yyyy').format(value.toLocal());

  /// "12 Aug 2026, 4:30 PM"
  static String dateTime(DateTime? value) => value == null
      ? '-'
      : DateFormat('d MMM yyyy, h:mm a').format(value.toLocal());

  /// "4:30 PM"
  static String time(DateTime? value) =>
      value == null ? '-' : DateFormat('h:mm a').format(value.toLocal());

  /// A deadline in plain words, which reads better than a bare date on a card.
  static String deadline(DateTime? value) {
    if (value == null) return 'No deadline set';
    final local = value.toLocal();
    final today = DateTime.now();
    final days = DateTime(local.year, local.month, local.day)
        .difference(DateTime(today.year, today.month, today.day))
        .inDays;

    if (days < 0) {
      final overdue = -days;
      return overdue == 1 ? 'Overdue by 1 day' : 'Overdue by $overdue days';
    }
    if (days == 0) return 'Due today';
    if (days == 1) return 'Due tomorrow';
    if (days <= 7) return 'Due in $days days';
    return 'Due ${dayMonth(local)}';
  }

  /// Bytes as "1.4 MB", for the upload preview.
  static String fileSize(int bytes) {
    if (bytes <= 0) return '0 KB';
    if (bytes < 1024) return '$bytes B';
    if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(0)} KB';
    return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
  }

  /// Cut long text for a card, without leaving a dangling half-word.
  static String truncate(String text, int max) {
    if (text.length <= max) return text;
    final cut = text.substring(0, max);
    final lastSpace = cut.lastIndexOf(' ');
    return '${lastSpace > max * 0.6 ? cut.substring(0, lastSpace) : cut}...';
  }
}
