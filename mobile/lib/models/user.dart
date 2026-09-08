import '../core/config/constants.dart';

/// A user as the backend returns it in `data.user` and from `/auth/me`.
///
/// Every field is read defensively: the officer and admin payloads carry keys
/// a student payload does not, and a missing one must not crash a screen.
class AppUser {
  const AppUser({
    required this.id,
    required this.name,
    required this.email,
    required this.role,
    this.userId = '',
    this.phone = '',
    this.department = '',
    this.userType = '',
    this.hostel = '',
    this.designation = '',
    this.isActive = true,
    this.emailVerified = false,
    this.createdAt,
  });

  final String id;
  final String name;
  final String email;
  final String role;
  final String userId;
  final String phone;
  final String department;
  final String userType;
  final String hostel;
  final String designation;
  final bool isActive;
  final bool emailVerified;
  final DateTime? createdAt;

  bool get isStudent => role == Domain.roleStudent;
  bool get isOfficer => role == Domain.roleOfficer;
  bool get isAdmin => role == Domain.roleAdmin;

  /// First letters of the name, for the avatar bubble.
  String get initials {
    final parts = name.trim().split(RegExp(r'\s+')).where((p) => p.isNotEmpty);
    if (parts.isEmpty) return '?';
    if (parts.length == 1) return parts.first[0].toUpperCase();
    return (parts.first[0] + parts.last[0]).toUpperCase();
  }

  factory AppUser.fromJson(Map<String, dynamic> json) {
    return AppUser(
      id: '${json['id'] ?? ''}',
      name: '${json['name'] ?? ''}',
      email: '${json['email'] ?? ''}',
      role: '${json['role'] ?? Domain.roleStudent}'.toLowerCase(),
      userId: '${json['userId'] ?? ''}',
      phone: '${json['phone'] ?? ''}',
      department: '${json['department'] ?? ''}',
      userType: '${json['userType'] ?? ''}',
      hostel: '${json['hostel'] ?? ''}',
      designation: '${json['designation'] ?? ''}',
      isActive: json['isActive'] != false,
      emailVerified: json['emailVerified'] == true,
      createdAt: DateTime.tryParse('${json['createdAt'] ?? ''}'),
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'email': email,
        'role': role,
        'userId': userId,
        'phone': phone,
        'department': department,
        'userType': userType,
        'hostel': hostel,
        'designation': designation,
        'isActive': isActive,
        'emailVerified': emailVerified,
        'createdAt': createdAt?.toIso8601String(),
      };
}
