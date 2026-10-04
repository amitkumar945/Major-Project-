/// An in-app notification, as `notification_service.create` stores it.
///
/// The in-app feed is the source of truth: MOBILE_API.md notes that when push
/// is unconfigured these still appear here, so the app never depends on FCM.
class AppNotification {
  const AppNotification({
    required this.id,
    required this.type,
    required this.title,
    required this.message,
    this.complaintId,
    this.createdAt,
    this.read = false,
  });

  final String id;
  final String type;
  final String title;
  final String message;
  final String? complaintId;
  final DateTime? createdAt;
  final bool read;

  factory AppNotification.fromJson(Map<String, dynamic> json) =>
      AppNotification(
        id: '${json['id'] ?? ''}',
        type: '${json['type'] ?? ''}',
        title: '${json['title'] ?? ''}',
        message: '${json['message'] ?? ''}',
        complaintId: json['complaintId'] == null
            ? null
            : '${json['complaintId']}',
        createdAt: DateTime.tryParse('${json['createdAt'] ?? ''}'),
        read: json['read'] == true,
      );

  AppNotification copyWith({bool? read}) => AppNotification(
        id: id,
        type: type,
        title: title,
        message: message,
        complaintId: complaintId,
        createdAt: createdAt,
        read: read ?? this.read,
      );
}
