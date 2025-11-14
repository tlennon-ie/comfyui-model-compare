# Changelog

All notable changes to ComfyUI Model Compare will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- (features to be added)

### Changed
- (changes to existing functionality)

### Fixed
- (bug fixes)

### Deprecated
- (soon-to-be removed features)

### Removed
- (removed features)

### Security
- (security fixes)

## [1.0.0] - 2024-01-15

### Added
- Initial release of ComfyUI Model Compare
- **Model Compare Loaders** node for defining comparison configurations
  - Support for multiple checkpoints (0-10)
  - Support for multiple VAEs (0-5)
  - Support for multiple text encoders (0-5)
  - Support for multiple LoRAs (0-10)
  
- **Model Compare Loaders Advanced** node for specific model selection
  - Dynamic widget generation based on configuration
  - LoRA strength configuration (comma-separated values)
  - Automatic combination generation using Cartesian product
  
- **Sampler Compare** node for batch sampling
  - Sampling across all model combinations
  - Support for different samplers (euler, dpmpp, etc.)
  - Automatic VAE decoding
  - Seed incrementation per combination
  
- **Grid Compare** node for result visualization
  - Customizable grid layout
  - Border styling (width, color)
  - Text labeling with custom fonts
  - Individual image saving option
  - Timestamped output directories
  
- Documentation
  - Comprehensive README with quick start guide
  - Technical documentation (TECHNICAL.md)
  - Setup and installation guide (SETUP.md)
  - Contributing guidelines (CONTRIBUTING.md)
  - Example workflow (example_workflow.json)

### Features Included
- ✅ Multi-checkpoint comparison
- ✅ Multi-VAE testing
- ✅ Multi-LoRA evaluation with configurable strengths
- ✅ Customizable grid appearance
- ✅ Batch processing
- ✅ Result archiving with timestamps
- ✅ Progress reporting

## Future Roadmap

### Version 1.1.0 (Q1 2024)
- [ ] Web UI components for result preview
- [ ] LoRA strength curve support (linear interpolation)
- [ ] Preset configurations library
- [ ] Advanced grid layouts (scatter plot style)

### Version 1.2.0 (Q2 2024)
- [ ] Video comparison support
- [ ] Statistical analysis (SSIM, LPIPS scores)
- [ ] Result comparison and diff visualization
- [ ] Batch workflow chaining

### Version 2.0.0 (Q3 2024)
- [ ] Multi-GPU distributed sampling
- [ ] Cloud storage integration
- [ ] Interactive web dashboard
- [ ] Model repository integration
- [ ] Advanced scheduling and queuing

## Known Issues

### Current Version (1.0.0)
- Grid generation may be slow for >100 images
- Memory usage can be high with many large models
- No support for batched VAE decoding yet
- Font loading is system-dependent

## Upgrading

### From Earlier Versions
No upgrade path yet (first release).

Future versions will include migration guides.

## Support

- **Questions?** Check the README.md or TECHNICAL.md
- **Found a bug?** Create an issue with reproduction steps
- **Have ideas?** Suggest features in discussions

---

## Version Details

### Version Numbering
- **MAJOR.MINOR.PATCH** (e.g., 1.0.0)
- MAJOR: Incompatible API changes
- MINOR: New features, backward compatible
- PATCH: Bug fixes only

### Release Schedule
- Releases every 4-6 weeks
- Security patches: As needed (out of schedule)
- Long-term support versions: TBD

### Deprecation Policy
- Features deprecated for 2+ releases before removal
- Clear warnings in logs when using deprecated features

## Credits

### Version 1.0.0
- Initial implementation and design
- Documentation and examples
- Community feedback integration

---

**Latest Version**: 1.0.0  
**Last Updated**: 2024-01-15  
**Maintainer**: [Your Name/GitHub]
