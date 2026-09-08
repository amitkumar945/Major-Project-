import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../core/network/api_exception.dart';
import '../../core/theme/app_theme.dart';
import '../../services/auth_service.dart';
import '../../widgets/common.dart';
import '../../widgets/state_views.dart';

/// Six-box OTP entry with a resend cooldown.
///
/// Returns the entered code through `Navigator.pop` once the server has
/// verified it, so the caller can carry on with whatever needed the
/// verification (a reset, a registration gate, or an OTP sign-in).
class OtpScreen extends StatefulWidget {
  const OtpScreen({
    super.key,
    required this.email,
    required this.purpose,
    this.title = 'Verify your email',
    this.devOtp,
  });

  final String email;
  final String purpose;
  final String title;

  /// Only ever populated in a development backend (`OTP_DEV_MODE`), where the
  /// API echoes the code back. Shown as a hint so testing does not need a
  /// mail server; in production this is always null.
  final String? devOtp;

  @override
  State<OtpScreen> createState() => _OtpScreenState();
}

class _OtpScreenState extends State<OtpScreen> {
  static const int _length = 6;
  static const int _cooldownSeconds = 30; // matches OTP_RESEND_COOLDOWN

  final List<TextEditingController> _controllers =
      List.generate(_length, (_) => TextEditingController());
  final List<FocusNode> _nodes = List.generate(_length, (_) => FocusNode());

  bool _verifying = false;
  String? _error;
  int _secondsLeft = _cooldownSeconds;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _startCooldown();

    // In dev mode the code is known, so it is pre-filled to save typing.
    final dev = widget.devOtp;
    if (dev != null && dev.length == _length) {
      for (var i = 0; i < _length; i++) {
        _controllers[i].text = dev[i];
      }
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    for (final c in _controllers) {
      c.dispose();
    }
    for (final n in _nodes) {
      n.dispose();
    }
    super.dispose();
  }

  void _startCooldown() {
    _timer?.cancel();
    setState(() => _secondsLeft = _cooldownSeconds);
    _timer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (!mounted) return timer.cancel();
      setState(() => _secondsLeft -= 1);
      if (_secondsLeft <= 0) timer.cancel();
    });
  }

  String get _code => _controllers.map((c) => c.text).join();

  void _onChanged(int index, String value) {
    setState(() => _error = null);

    // Handle a pasted code landing in one box.
    if (value.length > 1) {
      final digits = value.replaceAll(RegExp(r'\D'), '');
      for (var i = 0; i < _length; i++) {
        _controllers[i].text = i < digits.length ? digits[i] : '';
      }
      FocusScope.of(context).unfocus();
      if (_code.length == _length) _verify();
      return;
    }

    if (value.isNotEmpty && index < _length - 1) {
      _nodes[index + 1].requestFocus();
    }
    if (value.isEmpty && index > 0) {
      _nodes[index - 1].requestFocus();
    }
    if (_code.length == _length) {
      FocusScope.of(context).unfocus();
      _verify();
    }
  }

  Future<void> _verify() async {
    if (_code.length != _length || _verifying) return;

    setState(() {
      _verifying = true;
      _error = null;
    });

    try {
      final result = await AuthService.instance.verifyOtp(
        email: widget.email,
        otp: _code,
        purpose: widget.purpose,
      );
      if (!mounted) return;
      if (result.verified) {
        Navigator.of(context).pop(_code);
      } else {
        setState(() => _error = 'That code was not accepted. Please try again.');
      }
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _error = e.message);
      // A wrong code is worth clearing, so the user does not edit digit by digit.
      for (final c in _controllers) {
        c.clear();
      }
      _nodes.first.requestFocus();
    } finally {
      if (mounted) setState(() => _verifying = false);
    }
  }

  Future<void> _resend() async {
    if (_secondsLeft > 0) return;

    try {
      final result = await AuthService.instance
          .resendOtp(email: widget.email, purpose: widget.purpose);
      if (!mounted) return;

      _startCooldown();
      showSnack(context, 'A new code has been sent to ${widget.email}.');

      final dev = result['otp'];
      if (dev is String && dev.length == _length) {
        for (var i = 0; i < _length; i++) {
          _controllers[i].text = dev[i];
        }
        setState(() {});
      }
    } on ApiException catch (e) {
      if (!mounted) return;
      showSnack(context, e.message, isError: true);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(widget.title)),
      body: BusyOverlay(
        busy: _verifying,
        message: 'Checking your code...',
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(24, 16, 24, 32),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Container(
                width: 64,
                height: 64,
                decoration: BoxDecoration(
                  color: AppColors.brand50,
                  borderRadius: BorderRadius.circular(18),
                ),
                child: const Icon(Icons.mark_email_read_outlined,
                    size: 30, color: AppColors.brand600),
              ),
              const SizedBox(height: 20),

              const Text(
                'Enter the 6-digit code',
                style: TextStyle(
                  fontSize: 22,
                  fontWeight: FontWeight.w700,
                  color: AppColors.slate900,
                ),
              ),
              const SizedBox(height: 8),
              Text.rich(
                TextSpan(
                  style: const TextStyle(
                    fontSize: 15,
                    color: AppColors.slate500,
                    height: 1.5,
                  ),
                  children: [
                    const TextSpan(text: 'We sent a verification code to '),
                    TextSpan(
                      text: widget.email,
                      style: const TextStyle(
                        fontWeight: FontWeight.w600,
                        color: AppColors.slate700,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 28),

              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: List.generate(_length, (index) {
                  return SizedBox(
                    width: 48,
                    height: 58,
                    child: TextField(
                      controller: _controllers[index],
                      focusNode: _nodes[index],
                      autofocus: index == 0,
                      textAlign: TextAlign.center,
                      keyboardType: TextInputType.number,
                      inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                      style: const TextStyle(
                        fontSize: 22,
                        fontWeight: FontWeight.w700,
                        color: AppColors.slate900,
                      ),
                      decoration: const InputDecoration(
                        counterText: '',
                        contentPadding: EdgeInsets.zero,
                      ),
                      onChanged: (value) => _onChanged(index, value),
                    ),
                  );
                }),
              ),

              if (_error != null) ...[
                const SizedBox(height: 16),
                Text(
                  _error!,
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    fontSize: 14,
                    color: AppColors.red600,
                  ),
                ),
              ],

              const SizedBox(height: 28),
              FilledButton(
                onPressed: _verifying ? null : _verify,
                child: const Text('Verify'),
              ),
              const SizedBox(height: 16),

              Center(
                child: _secondsLeft > 0
                    ? Text(
                        'Resend code in ${_secondsLeft}s',
                        style: const TextStyle(
                          fontSize: 14,
                          color: AppColors.slate400,
                        ),
                      )
                    : TextButton(
                        onPressed: _resend,
                        child: const Text('Resend code'),
                      ),
              ),

              if (widget.devOtp != null) ...[
                const SizedBox(height: 24),
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: AppColors.amber50,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.info_outline_rounded,
                          size: 18, color: AppColors.amber500),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          'Development mode: the code is ${widget.devOtp}',
                          style: const TextStyle(
                            fontSize: 13,
                            color: AppColors.slate700,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
