from django.shortcuts import render, redirect, get_object_or_404
from users.models import UserProfile, ActivityLog
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from .utils import generate_full_resume, enhance_with_ollama
from .models import resume
from io import BytesIO
import json as _json


def _safe_json(value, fallback=None):
    """Parse a JSON string field safely; return fallback if it's plain text."""
    if fallback is None:
        fallback = []
    if not value:
        return fallback
    try:
        parsed = _json.loads(value)
        if isinstance(parsed, (list, dict)):
            return parsed
    except Exception:
        pass
    return value  # Return raw text as-is if it's not JSON (e.g., edited manually)


@login_required
def generate_resume(request):
    """Generate a new AI-enhanced resume from the user's profile."""
    try:
        profile = request.user.userprofile
    except UserProfile.DoesNotExist:
        return redirect('edit_profile')

    # Add loading indicator via GET parameter redirect pattern
    template_choice = profile.resume_template_choice or 1

    try:
        enhanced = generate_full_resume(profile, request.user.email)
    except Exception:
        from .utils import _plain_fallback
        enhanced = _plain_fallback(profile)

    # Save the generated resume — structured sections stored as JSON strings
    new_resume = resume.objects.create(
        user=request.user,
        full_name=profile.full_name,
        phone_number=profile.phone_number,
        email=request.user.email,
        location=profile.location,
        summary=enhanced.get('summary', ''),
        skills=_json.dumps(enhanced.get('skills', []), ensure_ascii=False),
        education=_json.dumps(enhanced.get('education', []), ensure_ascii=False),
        experience=_json.dumps(enhanced.get('experience', []), ensure_ascii=False),
        projects=_json.dumps(enhanced.get('projects', []), ensure_ascii=False),
        achievements=_json.dumps(enhanced.get('achievements', []), ensure_ascii=False),
        template_used=template_choice,
    )
    ActivityLog.objects.create(user=request.user, action='resume_generated')

    return redirect('view-resume', pk=new_resume.pk)


@login_required
def resume_details(request, pk):
    """View a single resume in the selected template."""
    my_resume = get_object_or_404(resume, pk=pk, user=request.user)

    template_choice = my_resume.template_used or 1
    template_name = f'resume_templates/template{template_choice}.html'

    context = {
        'resume': my_resume,
        'full_name': my_resume.full_name,
        'phone_number': my_resume.phone_number,
        'email': my_resume.email,
        'location': my_resume.location,
        'summary': my_resume.summary,
        # Parse structured JSON fields for template rendering
        'skills': _safe_json(my_resume.skills, []),
        'education': _safe_json(my_resume.education, []),
        'experience': _safe_json(my_resume.experience, []),
        'projects': _safe_json(my_resume.projects, []),
        'achievements': _safe_json(my_resume.achievements, []),
        'resume_id': my_resume.pk,
    }

    return render(request, template_name, context)


@login_required
def edit_resume(request, pk):
    """Edit a saved resume — all fields are editable inline."""
    my_resume = get_object_or_404(resume, pk=pk, user=request.user)

    if request.method == 'POST':
        my_resume.full_name = request.POST.get('full_name', my_resume.full_name)
        my_resume.phone_number = request.POST.get('phone_number', my_resume.phone_number)
        my_resume.email = request.POST.get('email', my_resume.email)
        my_resume.location = request.POST.get('location', my_resume.location)
        my_resume.summary = request.POST.get('summary', my_resume.summary)
        my_resume.skills = request.POST.get('skills', my_resume.skills)
        my_resume.education = request.POST.get('education', my_resume.education)
        my_resume.experience = request.POST.get('experience', my_resume.experience)
        my_resume.projects = request.POST.get('projects', my_resume.projects)
        my_resume.achievements = request.POST.get('achievements', my_resume.achievements)

        template_used = request.POST.get('template_used')
        if template_used:
            my_resume.template_used = int(template_used)

        my_resume.save()
        return redirect('view-resume', pk=my_resume.pk)

    context = {
        'resume': my_resume,
    }
    return render(request, 'resume_templates/edit_resume.html', context)


@login_required
def view_resume(request):
    """List all saved resumes."""
    allresume = resume.objects.filter(user=request.user)
    return render(request, 'resume_templates/view_resume.html', {'allresume': allresume})


@login_required
def delete_resume(request, pk):
    """Delete a saved resume."""
    resume.objects.filter(pk=pk, user=request.user).delete()
    return redirect('view')


@login_required
def download_resume_docx(request, pk=None):
    """Download a resume as a professionally formatted DOCX."""
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor, Cm
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    if pk:
        my_resume = get_object_or_404(resume, pk=pk, user=request.user)
    else:
        my_resume = resume.objects.filter(user=request.user).first()
        if not my_resume:
            return redirect('view')

    # Parse structured JSON sections
    skills_data = _safe_json(my_resume.skills, [])
    education_data = _safe_json(my_resume.education, [])
    experience_data = _safe_json(my_resume.experience, [])
    projects_data = _safe_json(my_resume.projects, [])
    achievements_data = _safe_json(my_resume.achievements, [])

    document = Document()

    # ── Page margins ────────────────────────────────────────────────
    section = document.sections[0]
    section.top_margin = Cm(1.8)
    section.bottom_margin = Cm(1.8)
    section.left_margin = Cm(2.0)
    section.right_margin = Cm(2.0)

    # ── Base font ────────────────────────────────────────────────────
    style = document.styles['Normal']
    style.font.name = 'Calibri'
    style.font.size = Pt(10.5)
    style.paragraph_format.space_after = Pt(0)

    def add_section_heading(text):
        """Add a bold, uppercase section heading with a bottom border line."""
        p = document.add_paragraph()
        p.paragraph_format.space_before = Pt(12)
        p.paragraph_format.space_after = Pt(3)
        run = p.add_run(text.upper())
        run.bold = True
        run.font.size = Pt(10)
        run.font.color.rgb = RGBColor(0x1E, 0x29, 0x3B)
        # Add bottom border via XML
        pPr = p._p.get_or_add_pPr()
        pBdr = OxmlElement('w:pBdr')
        bottom = OxmlElement('w:bottom')
        bottom.set(qn('w:val'), 'single')
        bottom.set(qn('w:sz'), '6')
        bottom.set(qn('w:space'), '1')
        bottom.set(qn('w:color'), '1E293B')
        pBdr.append(bottom)
        pPr.append(pBdr)
        return p

    def add_bullet(text, bold_start=None):
        """Add a bullet point. Optionally bold the first N characters."""
        p = document.add_paragraph(style='List Bullet')
        p.paragraph_format.left_indent = Inches(0.3)
        p.paragraph_format.space_after = Pt(1)
        if bold_start and text.startswith(bold_start):
            run1 = p.add_run(bold_start)
            run1.bold = True
            run1.font.size = Pt(10.5)
            run2 = p.add_run(text[len(bold_start):])
            run2.font.size = Pt(10.5)
        else:
            run = p.add_run(text)
            run.font.size = Pt(10.5)

    def add_role_header(title, company, dates):
        """Title (bold) | Company | dates on same line."""
        p = document.add_paragraph()
        p.paragraph_format.space_before = Pt(7)
        p.paragraph_format.space_after = Pt(1)
        if title:
            r = p.add_run(title)
            r.bold = True
            r.font.size = Pt(10.5)
        if company:
            r2 = p.add_run(f'  ·  {company}')
            r2.font.color.rgb = RGBColor(0x47, 0x55, 0x69)
            r2.font.size = Pt(10.5)
        if dates:
            tab_run = p.add_run(f'\t{dates}')
            tab_run.font.color.rgb = RGBColor(0x64, 0x74, 0x8B)
            tab_run.font.size = Pt(10)
            tab_run.italic = True
        p.paragraph_format.tab_stops.add_tab_stop(Inches(5.5), 2)  # Right-align date

    # ── NAME & CONTACT ───────────────────────────────────────────────
    name_p = document.add_paragraph()
    name_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    name_run = name_p.add_run(my_resume.full_name.upper())
    name_run.bold = True
    name_run.font.size = Pt(22)
    name_run.font.color.rgb = RGBColor(0x1E, 0x29, 0x3B)

    contact_parts = [x for x in [my_resume.email, my_resume.phone_number, my_resume.location] if x]
    contact_p = document.add_paragraph('  |  '.join(contact_parts))
    contact_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    contact_p.runs[0].font.size = Pt(9.5)
    contact_p.runs[0].font.color.rgb = RGBColor(0x64, 0x74, 0x8B)
    contact_p.paragraph_format.space_after = Pt(4)

    # ── PROFESSIONAL SUMMARY ─────────────────────────────────────────
    if my_resume.summary:
        add_section_heading('Professional Summary')
        p = document.add_paragraph(my_resume.summary)
        p.paragraph_format.space_after = Pt(2)
        p.runs[0].font.size = Pt(10.5)

    # ── SKILLS ───────────────────────────────────────────────────────
    if skills_data:
        add_section_heading('Skills')
        if isinstance(skills_data, list) and skills_data and isinstance(skills_data[0], dict):
            for cat in skills_data:
                p = document.add_paragraph()
                p.paragraph_format.space_after = Pt(2)
                cat_run = p.add_run(cat.get('category', '') + ': ')
                cat_run.bold = True
                cat_run.font.size = Pt(10.5)
                items_run = p.add_run(', '.join(cat.get('items', [])))
                items_run.font.size = Pt(10.5)
        else:
            # Fallback: plain text
            p = document.add_paragraph(str(skills_data))
            p.runs[0].font.size = Pt(10.5)

    # ── EDUCATION ────────────────────────────────────────────────────
    if education_data:
        add_section_heading('Education')
        if isinstance(education_data, list) and education_data and isinstance(education_data[0], dict):
            for edu in education_data:
                p = document.add_paragraph()
                p.paragraph_format.space_before = Pt(5)
                p.paragraph_format.space_after = Pt(1)
                inst_run = p.add_run(edu.get('institution', ''))
                inst_run.bold = True
                inst_run.font.size = Pt(10.5)
                degree = ' · '.join(filter(None, [edu.get('degree'), edu.get('field')]))
                if degree:
                    d_run = p.add_run(f'  ·  {degree}')
                    d_run.font.size = Pt(10.5)
                    d_run.font.color.rgb = RGBColor(0x47, 0x55, 0x69)
                if edu.get('dates'):
                    dt_run = p.add_run(f'  ·  {edu["dates"]}')
                    dt_run.italic = True
                    dt_run.font.color.rgb = RGBColor(0x64, 0x74, 0x8B)
                    dt_run.font.size = Pt(10)
        else:
            p = document.add_paragraph(str(education_data))
            p.runs[0].font.size = Pt(10.5)

    # ── EXPERIENCE ───────────────────────────────────────────────────
    if experience_data:
        add_section_heading('Professional Experience')
        if isinstance(experience_data, list) and experience_data and isinstance(experience_data[0], dict):
            for exp in experience_data:
                add_role_header(exp.get('title', ''), exp.get('company', ''), exp.get('dates', ''))
                for bullet in exp.get('bullets', []):
                    add_bullet(bullet)
        else:
            p = document.add_paragraph(str(experience_data))
            p.runs[0].font.size = Pt(10.5)

    # ── PROJECTS ─────────────────────────────────────────────────────
    if projects_data:
        add_section_heading('Projects')
        if isinstance(projects_data, list) and projects_data and isinstance(projects_data[0], dict):
            for proj in projects_data:
                p = document.add_paragraph()
                p.paragraph_format.space_before = Pt(7)
                p.paragraph_format.space_after = Pt(1)
                name_r = p.add_run(proj.get('name', ''))
                name_r.bold = True
                name_r.font.size = Pt(10.5)
                if proj.get('tech'):
                    tech_r = p.add_run(f'  ·  {proj["tech"]}')
                    tech_r.font.color.rgb = RGBColor(0x47, 0x55, 0x69)
                    tech_r.font.size = Pt(10)
                    tech_r.italic = True
                for bullet in proj.get('bullets', []):
                    add_bullet(bullet)
        else:
            p = document.add_paragraph(str(projects_data))
            p.runs[0].font.size = Pt(10.5)

    # ── ACHIEVEMENTS ─────────────────────────────────────────────────
    if achievements_data:
        add_section_heading('Achievements')
        if isinstance(achievements_data, list):
            for ach in achievements_data:
                add_bullet(str(ach))
        else:
            p = document.add_paragraph(str(achievements_data))
            p.runs[0].font.size = Pt(10.5)

    # ── Save & return ─────────────────────────────────────────────────
    buffer = BytesIO()
    document.save(buffer)
    buffer.seek(0)

    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )
    safe_name = my_resume.full_name.replace(' ', '_')
    response['Content-Disposition'] = f'attachment; filename="{safe_name}_Resume.docx"'
    return response