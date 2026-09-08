import 'dart:io';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../core/config/app_config.dart';
import '../core/theme/app_theme.dart';
import '../core/utils/formatters.dart';
import 'common.dart';

/// Camera and gallery attachments with a preview strip.
///
/// The size and count limits are the server's own (MAX_FILE_SIZE,
/// MAX_FILES_PER_REQUEST), checked here so an oversized photo is refused
/// instantly rather than after a slow upload on campus wifi.
class ImagePickerField extends StatefulWidget {
  const ImagePickerField({
    super.key,
    required this.files,
    required this.onChanged,
    this.maxFiles = AppConfig.maxFilesPerRequest,
    this.label = 'Photos (optional)',
    this.helper = 'Add up to 5 photos of the problem.',
  });

  final List<File> files;
  final ValueChanged<List<File>> onChanged;
  final int maxFiles;
  final String label;
  final String helper;

  @override
  State<ImagePickerField> createState() => _ImagePickerFieldState();
}

class _ImagePickerFieldState extends State<ImagePickerField> {
  final ImagePicker _picker = ImagePicker();
  bool _picking = false;

  Future<void> _pick(ImageSource source) async {
    if (widget.files.length >= widget.maxFiles) {
      showSnack(
        context,
        'You can attach at most ${widget.maxFiles} files.',
        isError: true,
      );
      return;
    }

    setState(() => _picking = true);
    try {
      if (source == ImageSource.gallery) {
        final picked = await _picker.pickMultiImage(
          imageQuality: 85,
          maxWidth: 1920,
        );
        if (picked.isEmpty) return;
        await _accept(picked);
      } else {
        final shot = await _picker.pickImage(
          source: ImageSource.camera,
          imageQuality: 85,
          maxWidth: 1920,
        );
        if (shot == null) return;
        await _accept([shot]);
      }
    } catch (e) {
      if (!mounted) return;
      // Usually a denied camera permission, which Android reports as a failure
      // to open rather than a typed error.
      showSnack(
        context,
        'Could not open ${source == ImageSource.camera ? 'the camera' : 'your gallery'}. Check the app permissions.',
        isError: true,
      );
    } finally {
      if (mounted) setState(() => _picking = false);
    }
  }

  /// Add what fits, and say clearly what was skipped and why.
  Future<void> _accept(List<XFile> picked) async {
    final accepted = <File>[...widget.files];
    final oversized = <String>[];
    var skippedForCount = 0;

    for (final item in picked) {
      if (accepted.length >= widget.maxFiles) {
        skippedForCount += 1;
        continue;
      }
      final file = File(item.path);
      final length = await file.length();
      if (length > AppConfig.maxFileSizeBytes) {
        oversized.add(item.name);
        continue;
      }
      accepted.add(file);
    }

    widget.onChanged(accepted);
    if (!mounted) return;

    if (oversized.isNotEmpty) {
      showSnack(
        context,
        oversized.length == 1
            ? '${oversized.first} is larger than ${Format.fileSize(AppConfig.maxFileSizeBytes)} and was skipped.'
            : '${oversized.length} files were larger than ${Format.fileSize(AppConfig.maxFileSizeBytes)} and were skipped.',
        isError: true,
      );
    } else if (skippedForCount > 0) {
      showSnack(
        context,
        'Only ${widget.maxFiles} files can be attached.',
        isError: true,
      );
    }
  }

  void _remove(int index) {
    final next = [...widget.files]..removeAt(index);
    widget.onChanged(next);
  }

  void _showSourceSheet() {
    showModalBottomSheet<void>(
      context: context,
      builder: (sheetContext) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const Icon(Icons.photo_camera_outlined,
                  color: AppColors.brand600),
              title: const Text('Take a photo',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.w500)),
              onTap: () {
                Navigator.of(sheetContext).pop();
                _pick(ImageSource.camera);
              },
            ),
            ListTile(
              leading: const Icon(Icons.photo_library_outlined,
                  color: AppColors.brand600),
              title: const Text('Choose from gallery',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.w500)),
              onTap: () {
                Navigator.of(sheetContext).pop();
                _pick(ImageSource.gallery);
              },
            ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final canAddMore = widget.files.length < widget.maxFiles;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          widget.label,
          style: const TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w600,
            color: AppColors.slate700,
          ),
        ),
        const SizedBox(height: 6),
        Text(
          widget.helper,
          style: const TextStyle(fontSize: 13, color: AppColors.slate500),
        ),
        const SizedBox(height: 12),

        if (widget.files.isNotEmpty)
          SizedBox(
            height: 96,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              itemCount: widget.files.length,
              separatorBuilder: (_, __) => const SizedBox(width: 10),
              itemBuilder: (context, index) => _preview(index),
            ),
          ),

        if (widget.files.isNotEmpty) const SizedBox(height: 12),

        if (canAddMore)
          OutlinedButton.icon(
            onPressed: _picking ? null : _showSourceSheet,
            icon: _picking
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.add_a_photo_outlined, size: 20),
            label: Text(
              widget.files.isEmpty ? 'Add photos' : 'Add another photo',
            ),
          )
        else
          Text(
            'Maximum ${widget.maxFiles} files attached.',
            style: const TextStyle(fontSize: 13, color: AppColors.slate400),
          ),
      ],
    );
  }

  Widget _preview(int index) {
    return Stack(
      children: [
        ClipRRect(
          borderRadius: BorderRadius.circular(10),
          child: Image.file(
            widget.files[index],
            width: 96,
            height: 96,
            fit: BoxFit.cover,
            errorBuilder: (_, __, ___) => Container(
              width: 96,
              height: 96,
              color: AppColors.slate100,
              child: const Icon(Icons.broken_image_outlined,
                  color: AppColors.slate400),
            ),
          ),
        ),
        Positioned(
          top: 2,
          right: 2,
          child: GestureDetector(
            onTap: () => _remove(index),
            child: Container(
              padding: const EdgeInsets.all(4),
              decoration: BoxDecoration(
                color: Colors.black.withValues(alpha: 0.6),
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.close_rounded,
                  size: 14, color: Colors.white),
            ),
          ),
        ),
      ],
    );
  }
}
