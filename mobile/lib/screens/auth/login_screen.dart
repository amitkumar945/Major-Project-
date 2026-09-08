import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/network/api_exception.dart';
import '../../core/theme/app_theme.dart';
import '../../providers/auth_provider.dart';
import '../../widgets/common.dart';
import '../../widgets/state_views.dart';
import 'forgot_password_screen.dart';
import 'register_screen.dart';

/// Sign-in. One identifier field, because the backend accepts an email or a
/// user id in `identifier` - asking the user which one they have would be a
/// question they should not need to answer.
class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _identifier = TextEditingController();
  final _password = TextEditingController();

  bool _obscure = true;
  bool _submitting = false;
  String? _formError;
  Map<String, String> _fieldErrors = {};

  @override
  void dispose() {
    _identifier.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    FocusScope.of(context).unfocus();

    // Local checks first, so an obviously empty form never costs a round trip.
    final errors = <String, String>{};
    if (_identifier.text.trim().isEmpty) {
      errors['identifier'] = 'Enter your email or user ID';
    }
    if (_password.text.isEmpty) {
      errors['password'] = 'Enter your password';
    }
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
      await context.read<AuthProvider>().signIn(
            identifier: _identifier.text,
            password: _password.text,
          );
      // The router reacts to the auth state, so there is no navigation here.
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _formError = e.message;
        _fieldErrors = e.fieldErrors;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _formError = 'Could not sign in. Please try again.');
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: BusyOverlay(
          busy: _submitting,
          message: 'Signing you in...',
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(24, 32, 24, 32),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const SizedBox(height: 16),
                _Logo(),
                const SizedBox(height: 32),

                const Text(
                  'Welcome back',
                  style: TextStyle(
                    fontSize: 26,
                    fontWeight: FontWeight.w700,
                    color: AppColors.slate900,
                  ),
                ),
                const SizedBox(height: 6),
                const Text(
                  'Sign in to raise and track your complaints.',
                  style: TextStyle(fontSize: 15, color: AppColors.slate500),
                ),
                const SizedBox(height: 28),

                if (_formError != null) ...[
                  _ErrorBanner(_formError!),
                  const SizedBox(height: 16),
                ],

                AppTextField(
                  controller: _identifier,
                  label: 'Email or User ID',
                  hint: 'you@dsvv.ac.in',
                  prefixIcon: Icons.person_outline_rounded,
                  keyboardType: TextInputType.emailAddress,
                  textInputAction: TextInputAction.next,
                  errorText: _fieldErrors['identifier'] ??
                      _fieldErrors['email'] ??
                      _fieldErrors['userId'],
                  enabled: !_submitting,
                ),
                const SizedBox(height: 18),

                AppTextField(
                  controller: _password,
                  label: 'Password',
                  hint: 'Your password',
                  prefixIcon: Icons.lock_outline_rounded,
                  obscureText: _obscure,
                  textInputAction: TextInputAction.done,
                  onSubmitted: (_) => _submit(),
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
                    tooltip: _obscure ? 'Show password' : 'Hide password',
                  ),
                ),

                Align(
                  alignment: Alignment.centerRight,
                  child: TextButton(
                    onPressed: _submitting
                        ? null
                        : () => Navigator.of(context).push(
                              MaterialPageRoute(
                                builder: (_) => const ForgotPasswordScreen(),
                              ),
                            ),
                    child: const Text('Forgot password?'),
                  ),
                ),
                const SizedBox(height: 8),

                FilledButton(
                  onPressed: _submitting ? null : _submit,
                  child: const Text('Sign in'),
                ),
                const SizedBox(height: 24),

                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const Text(
                      'New here?',
                      style: TextStyle(fontSize: 15, color: AppColors.slate500),
                    ),
                    TextButton(
                      onPressed: _submitting
                          ? null
                          : () => Navigator.of(context).push(
                                MaterialPageRoute(
                                  builder: (_) => const RegisterScreen(),
                                ),
                              ),
                      child: const Text('Create an account'),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _Logo extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Container(
          width: 64,
          height: 64,
          decoration: BoxDecoration(
            color: AppColors.brand600,
            borderRadius: BorderRadius.circular(18),
          ),
          child: const Icon(Icons.gavel_rounded, color: Colors.white, size: 32),
        ),
        const SizedBox(height: 14),
        const Text(
          'DSVV Grievance',
          style: TextStyle(
            fontSize: 19,
            fontWeight: FontWeight.w700,
            color: AppColors.slate900,
          ),
        ),
        const Text(
          'Dev Sanskriti Vishwavidyalaya',
          style: TextStyle(fontSize: 13, color: AppColors.slate500),
        ),
      ],
    );
  }
}

class _ErrorBanner extends StatelessWidget {
  const _ErrorBanner(this.message);

  final String message;

  @override
  Widget build(BuildContext context) {
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
