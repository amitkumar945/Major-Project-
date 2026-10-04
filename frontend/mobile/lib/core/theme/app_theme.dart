import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../config/constants.dart';

/// The app palette and Material 3 theme.
///
/// The university blue is lifted from `frontend/assets/css/tokens.css`, so the
/// Android app is recognisably the same product as the website without
/// imitating its desktop layout.
class AppColors {
  const AppColors._();

  static const Color brand50 = Color(0xFFEFF6FF);
  static const Color brand100 = Color(0xFFDBEAFE);
  static const Color brand500 = Color(0xFF3B82F6);
  static const Color brand600 = Color(0xFF1D4ED8);
  static const Color brand700 = Color(0xFF1E40AF);
  static const Color page = Color(0xFFF4F7FB);

  static const Color slate50 = Color(0xFFF8FAFC);
  static const Color slate100 = Color(0xFFF1F5F9);
  static const Color slate200 = Color(0xFFE2E8F0);
  static const Color slate400 = Color(0xFF94A3B8);
  static const Color slate500 = Color(0xFF64748B);
  static const Color slate600 = Color(0xFF475569);
  static const Color slate700 = Color(0xFF334155);
  static const Color slate900 = Color(0xFF0F172A);

  static const Color green600 = Color(0xFF16A34A);
  static const Color green50 = Color(0xFFF0FDF4);
  static const Color amber500 = Color(0xFFF59E0B);
  static const Color amber50 = Color(0xFFFFFBEB);
  static const Color red500 = Color(0xFFEF4444);
  static const Color red600 = Color(0xFFDC2626);
  static const Color red50 = Color(0xFFFEF2F2);
  static const Color sky600 = Color(0xFF0284C7);
  static const Color sky50 = Color(0xFFF0F9FF);
  static const Color violet600 = Color(0xFF7C3AED);
  static const Color violet50 = Color(0xFFF5F3FF);

  /// Colour for a complaint status. Grouped by meaning: waiting, working,
  /// done, and needs-attention, so the list scans at a glance.
  static Color forStatus(String status) {
    switch (status) {
      case Domain.statusSubmitted:
      case Domain.statusUnderReview:
        return sky600;
      case Domain.statusAssigned:
      case Domain.statusAccepted:
      case Domain.statusInProgress:
        return amber500;
      case Domain.statusResolved:
      case Domain.statusClosed:
        return green600;
      case Domain.statusPending:
        return slate500;
      case Domain.statusReopened:
      case Domain.statusEscalated:
        return red600;
      default:
        return slate500;
    }
  }

  static Color forStatusBackground(String status) {
    switch (status) {
      case Domain.statusSubmitted:
      case Domain.statusUnderReview:
        return sky50;
      case Domain.statusAssigned:
      case Domain.statusAccepted:
      case Domain.statusInProgress:
        return amber50;
      case Domain.statusResolved:
      case Domain.statusClosed:
        return green50;
      case Domain.statusReopened:
      case Domain.statusEscalated:
        return red50;
      default:
        return slate100;
    }
  }

  static Color forPriority(String priority) {
    switch (priority) {
      case Domain.priorityUrgent:
        return red600;
      case Domain.priorityHigh:
        return const Color(0xFFEA580C); // orange-600
      case Domain.priorityMedium:
        return amber500;
      case Domain.priorityLow:
        return green600;
      default:
        return slate500;
    }
  }

  static Color forDepartment(String department) {
    switch (department) {
      case 'Nirman Vibhag':
        return amber500;
      case 'Jal Kal Vibhag':
        return sky600;
      case 'Vidyut Vibhag':
        return const Color(0xFFCA8A04); // yellow-600
      case 'MCA Lab / Computer Lab':
        return violet600;
      default:
        return slate500;
    }
  }
}

class AppTheme {
  const AppTheme._();

  /// Comfortably above the 48dp Android minimum, since many users will be
  /// tapping these outdoors, one-handed, while looking at the problem.
  static const double minTouchTarget = 52;
  static const double cardRadius = 16;
  static const double fieldRadius = 12;

  static ThemeData light() {
    final scheme = ColorScheme.fromSeed(
      seedColor: AppColors.brand600,
      brightness: Brightness.light,
    ).copyWith(
      primary: AppColors.brand600,
      surface: Colors.white,
      error: AppColors.red600,
    );

    return ThemeData(
      useMaterial3: true,
      colorScheme: scheme,
      scaffoldBackgroundColor: AppColors.page,
      splashFactory: InkRipple.splashFactory,
      appBarTheme: const AppBarTheme(
        backgroundColor: Colors.white,
        foregroundColor: AppColors.slate900,
        elevation: 0,
        scrolledUnderElevation: 1,
        centerTitle: false,
        systemOverlayStyle: SystemUiOverlayStyle(
          statusBarColor: Colors.transparent,
          statusBarIconBrightness: Brightness.dark,
        ),
        titleTextStyle: TextStyle(
          color: AppColors.slate900,
          fontSize: 19,
          fontWeight: FontWeight.w600,
        ),
      ),
      cardTheme: CardThemeData(
        color: Colors.white,
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(cardRadius),
          side: const BorderSide(color: AppColors.slate200),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size.fromHeight(minTouchTarget),
          textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(fieldRadius),
          ),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          minimumSize: const Size.fromHeight(minTouchTarget),
          side: const BorderSide(color: AppColors.slate200),
          foregroundColor: AppColors.slate700,
          textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(fieldRadius),
          ),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: AppColors.brand600,
          minimumSize: const Size(64, 48),
          textStyle: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: Colors.white,
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(fieldRadius),
          borderSide: const BorderSide(color: AppColors.slate200),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(fieldRadius),
          borderSide: const BorderSide(color: AppColors.slate200),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(fieldRadius),
          borderSide: const BorderSide(color: AppColors.brand600, width: 2),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(fieldRadius),
          borderSide: const BorderSide(color: AppColors.red600),
        ),
        focusedErrorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(fieldRadius),
          borderSide: const BorderSide(color: AppColors.red600, width: 2),
        ),
        labelStyle: const TextStyle(color: AppColors.slate600, fontSize: 15),
        hintStyle: const TextStyle(color: AppColors.slate400, fontSize: 15),
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: Colors.white,
        indicatorColor: AppColors.brand50,
        height: 68,
        elevation: 3,
        labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
        labelTextStyle: WidgetStateProperty.resolveWith((states) {
          final selected = states.contains(WidgetState.selected);
          return TextStyle(
            fontSize: 12,
            fontWeight: selected ? FontWeight.w600 : FontWeight.w500,
            color: selected ? AppColors.brand700 : AppColors.slate500,
          );
        }),
        iconTheme: WidgetStateProperty.resolveWith((states) {
          final selected = states.contains(WidgetState.selected);
          return IconThemeData(
            size: 24,
            color: selected ? AppColors.brand700 : AppColors.slate500,
          );
        }),
      ),
      chipTheme: ChipThemeData(
        backgroundColor: AppColors.slate100,
        side: BorderSide.none,
        labelStyle: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(999),
        ),
      ),
      dialogTheme: DialogThemeData(
        backgroundColor: Colors.white,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
        ),
      ),
      bottomSheetTheme: const BottomSheetThemeData(
        backgroundColor: Colors.white,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
        ),
        showDragHandle: true,
      ),
      snackBarTheme: SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        backgroundColor: AppColors.slate900,
        contentTextStyle: const TextStyle(fontSize: 15, color: Colors.white),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(fieldRadius),
        ),
      ),
      dividerTheme: const DividerThemeData(
        color: AppColors.slate200,
        thickness: 1,
        space: 1,
      ),
      listTileTheme: const ListTileThemeData(
        minVerticalPadding: 12,
        iconColor: AppColors.slate500,
      ),
      progressIndicatorTheme:
          const ProgressIndicatorThemeData(color: AppColors.brand600),
    );
  }
}
