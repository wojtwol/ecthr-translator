# Translation Memory (TM)

This directory contains Translation Memory Exchange (TMX) files used by the ECTHR Translator system.

## What is Translation Memory?

Translation Memory stores previously translated segments to ensure consistency and speed up translation. When the system encounters a phrase that exists in TM, it automatically uses the stored translation.

## Files

### `polish_courts.tmx`
Standard translations for Polish court names. This ensures consistent terminology across all translations.

**Contents:**
- `district court` → `sąd rejonowy`
- `regional court` → `sąd okręgowy`
- `court of appeal` → `sąd apelacyjny`

Also includes:
- Capitalized variants (e.g., "District Court" → "Sąd Rejonowy")
- Location-specific variants (e.g., "Warsaw Court of Appeal" → "Sąd Apelacyjny w Warszawie")

## How to Use

### In Production
The system loads TM files from the configured `TM_PATH` (default: `/tmp/data/tm`).

To use these TM files:
1. Copy the TMX files to your TM directory
2. Restart the backend server
3. The system will automatically load and use these translations

### Adding New Terms

To add new translation pairs:
1. Edit an existing TMX file or create a new one
2. Add a new `<tu>` (translation unit) block:

```xml
<tu>
  <tuv xml:lang="en-US">
    <seg>your english term</seg>
  </tuv>
  <tuv xml:lang="pl-PL">
    <seg>twoje polskie tłumaczenie</seg>
  </tuv>
  <prop type="x-category">court_name</prop>
  <prop type="x-context">Brief context description</prop>
</tu>
```

3. Copy the file to your TM directory
4. Restart the backend

### File Format

TMX (Translation Memory eXchange) is an XML standard for translation memories. The basic structure:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE tmx SYSTEM "tmx14.dtd">
<tmx version="1.4">
  <header ... />
  <body>
    <tu>  <!-- Translation Unit -->
      <tuv xml:lang="en-US">  <!-- Source language -->
        <seg>source text</seg>
      </tuv>
      <tuv xml:lang="pl-PL">  <!-- Target language -->
        <seg>target text</seg>
      </tuv>
      <prop type="x-category">category</prop>  <!-- Optional metadata -->
    </tu>
  </body>
</tmx>
```

## Best Practices

1. **Case Sensitivity**: Include both lowercase and capitalized variants for terms that may appear in different contexts
2. **Context**: Use `<prop type="x-context">` to document where/how terms should be used
3. **Categories**: Use `<prop type="x-category">` to group related terms
4. **Specificity**: For institution names, include location-specific variants (e.g., "Warsaw District Court")
5. **Consistency**: Follow existing naming conventions in your TMX files

## Categories Used

- `court_name` - Names of courts and judicial institutions
- `procedural` - Procedural legal terms
- `ecthr_specific` - Terms specific to European Court of Human Rights
- `convention` - Convention articles and legal instruments

## Priority

When multiple translations exist for the same term, the system prioritizes:
1. **TM (exact)** - Exact match in Translation Memory (highest priority)
2. **HUDOC** - ECHR case law database
3. **CURIA** - CJEU case law database
4. **IATE** - EU terminology database
5. **Proposed** - AI-generated suggestion (lowest priority)

Translation Memory entries always take precedence over other sources.
