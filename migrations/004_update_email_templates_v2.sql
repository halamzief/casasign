-- SignCasa Signatures - Database Migration 004
-- Update email templates: remove Kaution, add company name, fix variable names
-- Created: 2026-03-24

-- ============================================================================
-- Update signature_request template
-- Changes:
--   - Remove Kaution/ads sections (not appropriate for signing invitation)
--   - Use sender_name (actual variable) instead of landlord_name
--   - Add company_name display
--   - Use property_address for object info
--   - Use expires_days variable (default 30)
--   - Clean, professional design
-- ============================================================================

UPDATE email_templates
SET
  name = 'Signature Request - Clean Professional',
  description = 'Clean signing invitation email without ads or Kaution info',
  subject_template = 'Mietvertrag zur Unterschrift{% if property_address %}: {{ property_address }}{% endif %}',
  body_html = '<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; line-height: 1.6; color: #1e293b; background-color: #f8fafc; }
        .wrapper { max-width: 600px; margin: 0 auto; padding: 20px; }
        .card { background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
        .header { background-color: #1e293b; padding: 28px 32px; }
        .header h1 { margin: 0; color: #ffffff; font-size: 20px; font-weight: 600; }
        .content { padding: 32px; }
        .info-box { background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 16px 20px; margin: 20px 0; }
        .info-label { font-size: 11px; font-weight: 600; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px; }
        .info-value { font-size: 15px; font-weight: 500; color: #1e293b; }
        .btn { display: inline-block; padding: 14px 32px; background-color: #f59e0b; color: #1e293b; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 15px; }
        .footer { text-align: center; padding: 24px 32px; color: #94a3b8; font-size: 12px; border-top: 1px solid #f1f5f9; }
        .footer a { color: #94a3b8; }
    </style>
</head>
<body>
    <div class="wrapper">
        <div class="card">
            <div class="header">
                <h1>Mietvertrag zur Unterschrift</h1>
            </div>

            <div class="content">
                <p>Hallo {{ signer_name }},</p>

                <p>{{ sender_name }}{% if company_name %} ({{ company_name }}){% endif %} hat einen Mietvertrag f&uuml;r Sie zur digitalen Unterschrift bereitgestellt.</p>

                {% if property_address %}
                <div class="info-box">
                    <div class="info-label">Objekt</div>
                    <div class="info-value">{{ property_address }}</div>
                </div>
                {% endif %}

                <p>Bitte pr&uuml;fen Sie den Vertrag sorgf&auml;ltig und unterschreiben Sie digital:</p>

                <div style="text-align: center; margin: 28px 0;">
                    <a href="{{ signing_link }}" class="btn">Vertrag ansehen &amp; unterschreiben</a>
                </div>

                <p style="color: #64748b; font-size: 13px;">Dieser Link ist {{ expires_days | default(30) }} Tage g&uuml;ltig. Bei Fragen wenden Sie sich direkt an Ihren Vermieter.</p>
            </div>

            <div class="footer">
                <p>SignCasa &ndash; Digitale Mietvertr&auml;ge leicht gemacht</p>
                <p><a href="{{ unsubscribe_link }}">Abmelden</a></p>
            </div>
        </div>
    </div>
</body>
</html>',
  body_text = 'Hallo {{ signer_name }},

{{ sender_name }}{% if company_name %} ({{ company_name }}){% endif %} hat einen Mietvertrag fuer Sie zur digitalen Unterschrift bereitgestellt.
{% if property_address %}
Objekt: {{ property_address }}
{% endif %}
Bitte pruefen Sie den Vertrag sorgfaeltig und unterschreiben Sie digital:

{{ signing_link }}

Dieser Link ist {{ expires_days | default(30) }} Tage gueltig. Bei Fragen wenden Sie sich direkt an Ihren Vermieter.

---
SignCasa - Digitale Mietvertraege leicht gemacht
Abmelden: {{ unsubscribe_link }}',
  updated_at = NOW()
WHERE template_key = 'signature_request'
  AND language = 'de'
  AND is_default = TRUE;

-- ============================================================================
-- Update signature_reminder template
-- Fix variable name: landlord_name -> sender_name + company_name
-- ============================================================================

UPDATE email_templates
SET
  body_html = '<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <style>
        body { margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; line-height: 1.6; color: #1e293b; background-color: #f8fafc; }
        .wrapper { max-width: 600px; margin: 0 auto; padding: 20px; }
        .card { background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
        .header { background-color: #f59e0b; padding: 28px 32px; }
        .header h1 { margin: 0; color: #1e293b; font-size: 20px; font-weight: 600; }
        .content { padding: 32px; }
        .urgent { background-color: #fef3c7; border-left: 4px solid #f59e0b; padding: 15px 20px; margin: 20px 0; border-radius: 0 6px 6px 0; }
        .btn { display: inline-block; padding: 14px 32px; background-color: #f59e0b; color: #1e293b; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 15px; }
        .footer { text-align: center; padding: 24px 32px; color: #94a3b8; font-size: 12px; border-top: 1px solid #f1f5f9; }
    </style>
</head>
<body>
    <div class="wrapper">
        <div class="card">
            <div class="header">
                <h1>Erinnerung: Unterschrift ausstehend</h1>
            </div>

            <div class="content">
                <p>Hallo {{ signer_name }},</p>

                <div class="urgent">
                    <p>Der Mietvertrag{% if property_address %} f&uuml;r <strong>{{ property_address }}</strong>{% endif %} wartet noch auf Ihre Unterschrift.</p>
                    {% if expires_at %}<p><strong>Der Link l&auml;uft ab am:</strong> {{ expires_at }}</p>{% endif %}
                </div>

                <div style="text-align: center; margin: 28px 0;">
                    <a href="{{ signing_link }}" class="btn">Jetzt unterschreiben</a>
                </div>

                <p style="color: #64748b; font-size: 13px;">Falls Sie Fragen haben, kontaktieren Sie bitte {{ sender_name }}{% if company_name %} ({{ company_name }}){% endif %} direkt.</p>
            </div>

            <div class="footer">
                <p>SignCasa &ndash; Digitale Mietvertr&auml;ge leicht gemacht</p>
            </div>
        </div>
    </div>
</body>
</html>',
  body_text = 'Hallo {{ signer_name }},

Der Mietvertrag{% if property_address %} fuer {{ property_address }}{% endif %} wartet noch auf Ihre Unterschrift.
{% if expires_at %}
Der Link laeuft ab am: {{ expires_at }}
{% endif %}
Jetzt unterschreiben: {{ signing_link }}

Falls Sie Fragen haben, kontaktieren Sie bitte {{ sender_name }}{% if company_name %} ({{ company_name }}){% endif %} direkt.

---
SignCasa - Digitale Mietvertraege leicht gemacht',
  updated_at = NOW()
WHERE template_key = 'signature_reminder'
  AND language = 'de'
  AND is_default = TRUE;
