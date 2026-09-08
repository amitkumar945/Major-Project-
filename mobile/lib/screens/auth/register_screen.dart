import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/config/constants.dart';
import '../../core/network/api_exception.dart';
import '../../core/theme/app_theme.dart';
import '../../providers/auth_provider.dart';
import '../../widgets/common.dart';
import '../../widgets/state_views.dart';

/// Create an account.
///
/// The field names match `validate_registration`: fullName, userId, email,
/// department and password are required; mobile is optional but validated if
/// given. Self-registration is always a student - the backend ignores any
/// other role without an admin token, so the app does not offer one.
class RegisterScreen extends StatefulWidget {
  const RegisterScreen({super.key});

  @override
  State<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends State<RegisterScreen> {
  final _fullName = TextEditingController();
  final _userId = TextEditingController();
  final _email = TextEditingController();
  final _mobile = TextEditingController();
  final _password = TextEditingController();
  final _confirm = TextEditingController();

  String _userType = 'Student';
  String? _course;
  bool _obscure = true;
  bool _submitting = false;
  String? _formError;
  Map<String, String> _fieldErrors = {};

  @override
  void dispose() {
    _fullName.dispose();
    _userId.dispose();
    _email.dispose();
    _mobile.dispose();
    _password.dispose();
    _confirm.dispose();
    super.dispose();
  }

  /// Mirrors the server rules, so the user sees problems before submitting.
  Map<String, String> _validate() {
    final errors = <String, String>{};

    final name = _fullName.text.trim();
    if (name.isEmpty) {
      errors['fullName'] = 'Full name is required';
    } else if (name.length < 3) {
      errors['fullName'] = 'Full name looks too short';
    }

    if (_userId.text.trim().isEmpty) {
      errors['userId'] = 'Student / Employee ID is required';
    }

    final email = _email.text.trim();
    if (email.isEmpty) {
      errors['email'] = 'Email address is required';
    } else if (!RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$').hasMatch(email)) {
      errors['email'] = 'Enter a valid email address';
    }

    if (_course == null || _course!.isEmpty) {
      errors['department'] = 'Please select your department or course';
    }

    if (_password.text.isEmpty) {
      errors['password'] = 'Password is required';
    } else if (_password.text.length < 8) {
      errors['password'] = 'Password must be at least 8 characters';
    }

    if (_confirm.text != _password.text) {
      errors['confirmPassword'] = 'Passwords do not match';
    }

    final mobile = _mobile.text.trim();
    if (mobile.isNotEmpty && !RegExp(r'^[6-9]\d{9}$').hasMatch(mobile)) {
      errors['mobile'] = 'Enter a valid 10-digit mobile number';
    }

    return errors;
  }

  Future<void> _submit() async {
    FocusScope.of(context).unfocus();

    final errors = _validate();
    if (errors.isNotEmpty) {
      setState(() {
        _fieldErrors = errors;
        _formError = null;
      });
      return;
    }

    setState(() {
      _submitting = true;
      _formError = null;
      _fieldErrors = {};
    });

    try {
      await context.read<AuthProvider>().register({
        'fullName': _fullName.text.trim(),
        'userId': _userId.text.trim(),
        'email': _email.text.trim(),
        'department': _course,
        'userType': _userType,
        'password': _password.text,
        if (_mobile.text.trim().isNotEmpty) 'mobile': _mobile.text.trim(),
      });
      // Registration signs the user straight in; the router takes over.
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _formError = e.message;
        _fieldErrors = e.fieldErrors;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _formError = 'Could not create your account. Please try again.');
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Create account')),
      body: BusyOverlay(
        busy: _submitting,
        message: 'Creating your account...',
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(24, 8, 24, 32),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text(
                'Register once, then raise and track any number of complaints.',
                style: TextStyle(
                  fontSize: 15,
                  color: AppColors.slate500,
                  height: 1.5,
                ),
              ),
              const SizedBox(height: 24),

              if (_formError != null) ...[
                Container(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: AppColors.red50,
                    borderRadius: BorderRadius.circular(12),
                    border:
                        Border.all(color: AppColors.red500.withValues(alpha: 0.3)),
                  ),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Icon(Icons.error_outline_rounded,
                          size: 20, color: AppColors.red600),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          _formError!,
                          style: const TextStyle(
                            fontSize: 14,
                            color: AppColors.red600,
                            height: 1.4,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 16),
              ],

              AppTextField(
                controller: _fullName,
                label: 'Full name',
                hint: 'As it appears on your ID card',
                prefixIcon: Icons.badge_outlined,
                textInputAction: TextInputAction.next,
                errorText: _fieldErrors['fullName'],
                enabled: !_submitting,
              ),
              const SizedBox(height: 18),

              AppTextField(
                controller: _userId,
                label: 'Student / Employee ID',
                hint: 'e.g. MCA2024001',
                prefixIcon: Icons.pin_outlined,
                textInputAction: TextInputAction.next,
                errorText: _fieldErrors['userId'],
                enabled: !_submitting,
              ),
              const SizedBox(height: 18),

              AppTextField(
                controller: _email,
                label: 'Email address',
                hint: 'you@dsvv.ac.in',
                prefixIcon: Icons.mail_outline_rounded,
                keyboardType: TextInputType.emailAddress,
                textInputAction: TextInputAction.next,
                errorText: _fieldErrors['email'],
                enabled: !_submitting,
                helperText: 'You will use this to sign in.',
              ),
              const SizedBox(height: 18),

              AppDropdown<String>(
                label: 'I am a',
                value: _userType,
                items: Domain.userTypes,
                onChanged: _submitting
                    ? (_) {}
                    : (value) => setState(() => _userType = value ?? 'Student'),
              ),
              const SizedBox(height: 18),

              AppDropdown<String>(
                label: 'Department / Course',
                value: _course,
                hint: 'Select your department or course',
                items: Domain.courses,
                errorText: _fieldErrors['department'],
                onChanged: _submitting
                    ? (_) {}
                    : (value) => setState(() => _course = value),
              ),
              const SizedBox(height: 18),

              AppTextField(
                controller: _mobile,
                label: 'Mobile number (optional)',
                hint: '10-digit number',
                prefixIcon: Icons.phone_outlined,
                keyboardType: TextInputType.phone,
                textInputAction: TextInputAction.next,
                maxLength: 10,
                errorText: _fieldErrors['mobile'],
                enabled: !_submitting,
              ),
              const SizedBox(height: 18),

              AppTextField(
                controller: _password,
                label: 'Password',
                hint: 'At least 8 characters',
                prefixIcon: Icons.lock_outline_rounded,
                obscureText: _obscure,
                textInputAction: TextInputAction.next,
                errorText: _fieldErrors['password'],
                enabled: !_submitting,
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
                label: 'Confirm password',
                hint: 'Re-enter your password',
                prefixIcon: Icons.lock_outline_rounded,
                obscureText: _obscure,
                textInputAction: TextInputAction.done,
                onSubmitted: (_) => _submit(),
                errorText: _fieldErrors['confirmPassword'],
                enabled: !_submitting,
              ),
              const SizedBox(height: 28),

              FilledButton(
                onPressed: _submitting ? null : _submit,
                child: const Text('Create account'),
              ),
              const SizedBox(height: 16),

              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Text(
                    'Already registered?',
                    style: TextStyle(fontSize: 15, color: AppColors.slate500),
                  ),
                  TextButton(
                    onPressed: _submitting
                        ? null
                        : () => Navigator.of(context).pop(),
                    child: const Text('Sign in'),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
