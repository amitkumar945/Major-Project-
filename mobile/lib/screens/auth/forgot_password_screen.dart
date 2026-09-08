import 'package:flutter/material.dart';

import '../../core/network/api_exception.dart';
import '../../core/theme/app_theme.dart';
import '../../services/auth_service.dart';
import '../../widgets/common.dart';
import '../../widgets/state_views.dart';
import 'otp_screen.dart';

/// Password reset: ask for the address, verify the emailed code, set a new
/// password.
///
/// The first step always reports success even for an unregistered address -
/// that is deliberate on the server so the endpoint cannot be used to discover
/// accounts, and the wording here matches it rather than implying delivery.
class ForgotPasswordScreen extends StatefulWidget {
  const ForgotPasswordScreen({super.key});

  @override
  State<ForgotPasswordScreen> createState() => _ForgotPasswordScreenState();
}

class _ForgotPasswordScreenState extends State<ForgotPasswordScreen> {
  final _email = TextEditingController();
  final _password = TextEditingController();
  final _confirm = TextEditingController();

  /// 0 = enter email, 1 = set the new password (after the code is verified).
  int _step = 0;
  String _verifiedOtp = '';
  bool _busy = false;
  bool _obscure = true;
  String? _error;
  Map<String, String> _fieldErrors = {};

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    _confirm.dispose();
    super.dispose();
  }

  Future<void> _sendCode() async {
    FocusScope.of(context).unfocus();

    final email = _email.text.trim();
    if (!RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$').hasMatch(email)) {
      setState(() => _fieldErrors = {'email': 'Enter a valid email address'});
      return;
    }

    setState(() {
      _busy = true;
      _error = null;
      _fieldErrors = {};
    });

    try {
      final result = await AuthService.instance.forgotPassword(email);
      if (!mounted) return;

      // `otp` is only present on a development backend.
      final devOtp = result['otp'] is String ? result['otp'] as String : null;

      final code = await Navigator.of(context).push<String>(
        MaterialPageRoute(
          builder: (_) => OtpScreen(
            email: email,
            purpose: AuthService.purposeReset,
            title: 'Reset your password',
            devOtp: devOtp,
          ),
        ),
      );

      if (!mounted) return;
      if (code != null && code.isNotEmpty) {
        setState(() {
          _verifiedOtp = code;
          _step = 1;
        });
      }
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _resetPassword() async {
    FocusScope.of(context).unfocus();

    final errors = <String, String>{};
    if (_password.text.length < 8) {
      errors['newPassword'] = 'Password must be at least 8 characters';
    }
    if (_confirm.text != _password.text) {
      errors['confirmPassword'] = 'Passwords do not match';
    }
    if (errors.isNotEmpty) {
      setState(() => _fieldErrors = errors);
      return;
    }

    setState(() {
      _busy = true;
      _error = null;
      _fieldErrors = {};
    });

    try {
      await AuthService.instance.resetPassword(
        email: _email.text.trim(),
        otp: _verifiedOtp,
        newPassword: _password.text,
      );
      if (!mounted) return;

      showSnack(context, 'Password reset. Please sign in with your new password.');
      Navigator.of(context).pop();
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.message;
        _fieldErrors = e.fieldErrors;
      });
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_step == 0 ? 'Forgot password' : 'New password'),
      ),
      body: BusyOverlay(
        busy: _busy,
        message: _step == 0 ? 'Sending code...' : 'Saving your password...',
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(24, 16, 24, 32),
          child: _step == 0 ? _emailStep() : _passwordStep(),
        ),
      ),
    );
  }

  Widget _emailStep() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Container(
          width: 64,
          height: 64,
          decoration: BoxDecoration(
            color: AppColors.brand50,
            borderRadius: BorderRadius.circular(18),
          ),
          child: const Icon(Icons.lock_reset_rounded,
              size: 30, color: AppColors.brand600),
        ),
        const SizedBox(height: 20),
        const Text(
          'Reset your password',
          style: TextStyle(
            fontSize: 22,
            fontWeight: FontWeight.w700,
            color: AppColors.slate900,
          ),
        ),
        const SizedBox(height: 8),
        const Text(
          'Enter your registered email address and we will send you a verification code.',
          style: TextStyle(fontSize: 15, color: AppColors.slate500, height: 1.5),
        ),
        const SizedBox(height: 28),

        if (_error != null) ...[
          _banner(_error!),
          const SizedBox(height: 16),
        ],

        AppTextField(
          controller: _email,
          label: 'Email address',
          hint: 'you@dsvv.ac.in',
          prefixIcon: Icons.mail_outline_rounded,
          keyboardType: TextInputType.emailAddress,
          textInputAction: TextInputAction.done,
          onSubmitted: (_) => _sendCode(),
          errorText: _fieldErrors['email'],
          enabled: !_busy,
        ),
        const SizedBox(height: 24),

        FilledButton(
          onPressed: _busy ? null : _sendCode,
          child: const Text('Send code'),
        ),
      ],
    );
  }

  Widget _passwordStep() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Container(
          width: 64,
          height: 64,
          decoration: BoxDecoration(
            color: AppColors.green50,
            borderRadius: BorderRadius.circular(18),
          ),
          child: const Icon(Icons.verified_outlined,
              size: 30, color: AppColors.green600),
        ),
        const SizedBox(height: 20),
        const Text(
          'Choose a new password',
          style: TextStyle(
            fontSize: 22,
            fontWeight: FontWeight.w700,
            color: AppColors.slate900,
          ),
        ),
        const SizedBox(height: 8),
        const Text(
          'Your code was verified. Set a new password to finish.',
          style: TextStyle(fontSize: 15, color: AppColors.slate500, height: 1.5),
        ),
        const SizedBox(height: 28),

        if (_error != null) ...[
          _banner(_error!),
          const SizedBox(height: 16),
        ],

        AppTextField(
          controller: _password,
          label: 'New password',
          hint: 'At least 8 characters',
          prefixIcon: Icons.lock_outline_rounded,
          obscureText: _obscure,
          textInputAction: TextInputAction.next,
          errorText: _fieldErrors['newPassword'],
          enabled: !_busy,
          suffixIcon: IconButton(
            icon: Icon(
              _obscure
                  ? Icons.visibility_outlined
                  : Icons.visibility_off_outlined,
              size: 20,
              color: AppColors.slate400,
            ),
            onPressed: () => setState(() => _obscure = !_obscure),
          ),
        ),
        const SizedBox(height: 18),

        AppTextField(
          controller: _confirm,
          label: 'Confirm new password',
          hint: 'Re-enter your password',
          prefixIcon: Icons.lock_outline_rounded,
          obscureText: _obscure,
          textInputAction: TextInputAction.done,
          onSubmitted: (_) => _resetPassword(),
          errorText: _fieldErrors['confirmPassword'],
          enabled: !_busy,
        ),
        const SizedBox(height: 28),

        FilledButton(
          onPressed: _busy ? null : _resetPassword,
          child: const Text('Reset password'),
        ),
      ],
    );
  }

  Widget _banner(String message) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.red50,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.red500.withValues(alpha: 0.3)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.error_outline_rounded,
              size: 20, color: AppColors.red600),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              message,
              style: const TextStyle(
                fontSize: 14,
                color: AppColors.red600,
                height: 1.4,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
