-- SignCasa Signatures - Database Migration 002
-- Seed Email Templates
-- Created: 2025-11-23

-- ============================================================================
-- Default Email Template: Signature Request (Tenant)
-- Includes utilities + insurance opt-in messaging
-- ============================================================================
INSERT INTO email_templates (
  template_key,
  name,
  description,
  subject_template,
  body_html,
  body_text,
  language,
  is_default,
  is_active
) VALUES (
  'signature_request',
  'Signature Request - Tenant (Default with Utilities + Insurance)',
  'Email sent to tenants to sign rental contract with insurance and utilities opt-in offers',
  'Mietvertrag zur Unterschrift: {{ property_address }}',
  '<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background-color: #2563eb; color: white; padding: 20px; text-align: center; }
        .content { padding: 30px 20px; background-color: #f9fafb; }
        .button { display: inline-block; padding: 15px 30px; background-color: #2563eb; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }
        .benefits { background-color: #eff6ff; border-left: 4px solid #2563eb; padding: 15px; margin: 20px 0; }
        .ads { background-color: #fef3c7; border: 1px solid #f59e0b; padding: 15px; margin: 20px 0; border-radius: 5px; }
        .footer { text-align: center; padding: 20px; color: #6b7280; font-size: 12px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏡 Mietvertrag zur Unterschrift</h1>
        </div>

        <div class="content">
            <p>Hallo {{ signer_name }},</p>

            <p><strong>{{ landlord_name }}</strong> hat Ihnen einen Mietvertrag für die Wohnung <strong>{{ property_address }}</strong> zur Unterschrift gesendet.</p>

            <div class="benefits">
                <h3>💰 Beim Unterschreiben verfügbar:</h3>
                <ul>
                    <li><strong>Kautionsversicherung</strong> - Statt {{ kaution_amount }}€ Kaution nur 10-20€/Monat</li>
                    <li><strong>Strom & Gas</strong> - Bis zu 300€ Wechselbonus</li>
                    <li><strong>Internet & Telefon</strong> - Beste Tarife vergleichen</li>
                    <li><strong>Haftpflichtversicherung</strong> - Ab 5€/Monat</li>
                </ul>
                <p><small>Optional und kostenlos - Sie sparen sich ~4 Stunden Arbeit!</small></p>
            </div>

            <div style="text-align: center;">
                <a href="{{ signing_link }}" class="button">Jetzt Vertrag ansehen & unterschreiben →</a>
            </div>

            <p><strong>Wichtig:</strong> Der Link ist 7 Tage gültig.</p>

            <!-- Free tier: Ads section -->
            <div class="ads">
                <h4>🚀 Partner-Angebote für Ihren Umzug</h4>
                <ul>
                    <li><strong>Umzugsservice</strong> - Bis zu 40% sparen mit Vergleichsportalen</li>
                    <li><strong>Hausratversicherung</strong> - Schützen Sie Ihr Eigentum ab 5€/Monat</li>
                    <li><strong>Nachsendeauftrag</strong> - Post automatisch weiterleiten lassen</li>
                </ul>
                <p><small>Diese Angebote helfen uns, SignCasa kostenlos anzubieten.</small></p>
            </div>
        </div>

        <div class="footer">
            <p>SignCasa - Digitale Mietverträge leicht gemacht</p>
            <p><a href="{{ unsubscribe_link }}">Abmelden</a></p>
            <p><small>Diese E-Mail wurde an {{ signer_email }} gesendet.</small></p>
        </div>
    </div>
</body>
</html>',
  'Hallo {{ signer_name }},

{{ landlord_name }} hat Ihnen einen Mietvertrag für {{ property_address }} zur Unterschrift gesendet.

Beim Unterschreiben verfügbar:
- Kautionsversicherung - Statt {{ kaution_amount }}€ Kaution nur 10-20€/Monat
- Strom & Gas - Bis zu 300€ Wechselbonus
- Internet & Telefon - Beste Tarife vergleichen
- Haftpflichtversicherung - Ab 5€/Monat

Jetzt unterschreiben: {{ signing_link }}

Der Link ist 7 Tage gültig.

---
SignCasa - Digitale Mietverträge leicht gemacht
Abmelden: {{ unsubscribe_link }}',
  'de',
  TRUE,
  TRUE
);

-- ============================================================================
-- Email Template: Signature Completed
-- ============================================================================
INSERT INTO email_templates (
  template_key,
  name,
  description,
  subject_template,
  body_html,
  body_text,
  language,
  is_default,
  is_active
) VALUES (
  'signature_completed',
  'Signature Completed Confirmation',
  'Email sent when all parties have signed the contract',
  'Mietvertrag vollständig unterschrieben: {{ property_address }}',
  '<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background-color: #10b981; color: white; padding: 20px; text-align: center; }
        .content { padding: 30px 20px; }
        .success { background-color: #d1fae5; border-left: 4px solid #10b981; padding: 15px; margin: 20px 0; }
        .button { display: inline-block; padding: 15px 30px; background-color: #10b981; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>✅ Mietvertrag vollständig unterschrieben!</h1>
        </div>

        <div class="content">
            <p>Hallo {{ recipient_name }},</p>

            <div class="success">
                <p><strong>Gute Nachrichten!</strong> Alle Parteien haben den Mietvertrag für <strong>{{ property_address }}</strong> unterschrieben.</p>
            </div>

            <p><strong>Unterschrieben von:</strong></p>
            <ul>
                {% for signer in signers %}
                <li>{{ signer.name }} ({{ signer.role }}) - {{ signer.signed_at }}</li>
                {% endfor %}
            </ul>

            <div style="text-align: center;">
                <a href="{{ download_link }}" class="button">Vertrag herunterladen</a>
            </div>

            <p><strong>Nächste Schritte:</strong></p>
            <ul>
                <li>Zählerstände bei Einzug notieren</li>
                <li>Übergabeprotokoll erstellen</li>
                <li>Versicherungen prüfen</li>
            </ul>
        </div>

        <div style="text-align: center; padding: 20px; color: #6b7280; font-size: 12px;">
            <p>SignCasa - Digitale Mietverträge leicht gemacht</p>
        </div>
    </div>
</body>
</html>',
  'Hallo {{ recipient_name }},

Gute Nachrichten! Alle Parteien haben den Mietvertrag für {{ property_address }} unterschrieben.

Unterschrieben von:
{% for signer in signers %}
- {{ signer.name }} ({{ signer.role }}) - {{ signer.signed_at }}
{% endfor %}

Vertrag herunterladen: {{ download_link }}

Nächste Schritte:
- Zählerstände bei Einzug notieren
- Übergabeprotokoll erstellen
- Versicherungen prüfen

---
SignCasa - Digitale Mietverträge leicht gemacht',
  'de',
  TRUE,
  TRUE
);

-- ============================================================================
-- Email Template: Signing Reminder
-- ============================================================================
INSERT INTO email_templates (
  template_key,
  name,
  description,
  subject_template,
  body_html,
  body_text,
  language,
  is_default,
  is_active
) VALUES (
  'signature_reminder',
  'Signature Reminder',
  'Reminder email for unsigned contracts',
  'Erinnerung: Mietvertrag wartet auf Ihre Unterschrift',
  '<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background-color: #f59e0b; color: white; padding: 20px; text-align: center; }
        .content { padding: 30px 20px; }
        .urgent { background-color: #fef3c7; border-left: 4px solid #f59e0b; padding: 15px; margin: 20px 0; }
        .button { display: inline-block; padding: 15px 30px; background-color: #f59e0b; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>⏰ Erinnerung: Unterschrift ausstehend</h1>
        </div>

        <div class="content">
            <p>Hallo {{ signer_name }},</p>

            <div class="urgent">
                <p>Der Mietvertrag für <strong>{{ property_address }}</strong> wartet noch auf Ihre Unterschrift.</p>
                <p><strong>Der Link läuft ab am:</strong> {{ expires_at }}</p>
            </div>

            <div style="text-align: center;">
                <a href="{{ signing_link }}" class="button">Jetzt unterschreiben</a>
            </div>

            <p>Falls Sie Fragen haben, kontaktieren Sie bitte {{ landlord_name }} direkt.</p>
        </div>

        <div style="text-align: center; padding: 20px; color: #6b7280; font-size: 12px;">
            <p>SignCasa - Digitale Mietverträge leicht gemacht</p>
        </div>
    </div>
</body>
</html>',
  'Hallo {{ signer_name }},

Der Mietvertrag für {{ property_address }} wartet noch auf Ihre Unterschrift.

Der Link läuft ab am: {{ expires_at }}

Jetzt unterschreiben: {{ signing_link }}

Falls Sie Fragen haben, kontaktieren Sie bitte {{ landlord_name }} direkt.

---
SignCasa - Digitale Mietverträge leicht gemacht',
  'de',
  TRUE,
  TRUE
);

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON COLUMN email_templates.template_key IS 'Unique identifier for template type';
COMMENT ON COLUMN email_templates.is_default IS 'TRUE = includes ads (free tier), FALSE = no ads (premium)';
COMMENT ON COLUMN email_templates.body_html IS 'Jinja2 HTML template with variables';
COMMENT ON COLUMN email_templates.body_text IS 'Plain text fallback for email clients';
