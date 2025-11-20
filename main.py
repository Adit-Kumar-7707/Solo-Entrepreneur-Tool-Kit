import csv
import datetime as dt
import os
import random as r
import re
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INVOICE_TEMPLATE_PATH = os.path.join(BASE_DIR, "invoiceTemplate.tex")
INVOICE_HISTORY_PATH = os.path.join(BASE_DIR, "invoiceHistory.csv")
MONEY_FLOW_PATH = os.path.join(BASE_DIR, "moneyFlow.csv")
LOGO_PATH = os.path.join(BASE_DIR, "logo.png")


INVOICE_FIELD_KEYS = [
    ("Company Name", "companyName"),
    ("Company Address", "companyAddress"),
    ("Company City", "companyCity"),
    ("Company Country", "companyCountry"),
    ("Company Postal", "companyPostal"),
    ("Bill To Name", "billToName"),
    ("Bill To Address", "billToAddress"),
    ("Bill To City", "billToCity"),
    ("Bill To Country", "billToCountry"),
    ("Bill To Postal", "billToPostal"),
    ("Invoice Number", "invoiceNumber"),
    ("Invoice Date", "invoiceDate"),
    ("Invoice Due Date", "invoiceDueDate"),
    ("Total Amount", "totalAmount"),
]


def blank_invoice_fields():
    return {key: "" for _, key in INVOICE_FIELD_KEYS} | {"notesText": ""}


def render_invoice_tex(fields, items):
    if not os.path.exists(INVOICE_TEMPLATE_PATH):
        raise FileNotFoundError("invoiceTemplate.tex is missing.")

    with open(INVOICE_TEMPLATE_PATH, "r", encoding="utf-8") as template_file:
        tex = template_file.read()

    for key, val in fields.items():
        pattern = r"(\\newcommand\{\\" + re.escape(key) + r"\}\{)[^\}]*\}"

        def repl(match, value=val):
            return match.group(1) + (value or "") + "}"

        tex = re.sub(pattern, repl, tex)

    rows = []
    for item in items:
        row = (
            f"{{{item['itemName']}}}&"
            f"{{{item['description']}}}&"
            f"{{{item['quantity']}}}&"
            f"{{₹{item['price']}}}&"
            f"{{{item['tax']}\\%}}&"
            f"{{₹{item['amount']}}}\\\\"
        )
        rows.append(row)

    if not rows:
        rows.append("{No items added}&{}&{}&{}&{}&{}\\\\")

    tex = tex.replace("%%ITEM_ROWS%%", "\n".join(rows))

    invoice_number = fields.get("invoiceNumber") or dt.datetime.now().strftime("%Y%m%d%H%M")
    safe_invoice_number = str(invoice_number).replace("/", "-").strip() or "0000"
    output_tex_path = os.path.join(BASE_DIR, f"invoice_{safe_invoice_number}.tex")
    with open(output_tex_path, "w", encoding="utf-8") as tex_file:
        tex_file.write(tex)
    return output_tex_path


def compile_tex_to_pdf(tex_path):
    work_dir = os.path.dirname(tex_path)
    tex_name = os.path.basename(tex_path)
    pdf_path = os.path.splitext(tex_path)[0] + ".pdf"
    base_name = os.path.splitext(tex_name)[0]
    
    try:
        # Use timeout to prevent hanging (60 seconds should be enough)
        subprocess_kwargs = {
            "args": ["xelatex", "-interaction=batchmode", "-halt-on-error", tex_name],
            "cwd": work_dir,
            "check": False,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "text": True,
            "timeout": 60,
        }
        # Add CREATE_NO_WINDOW flag on Windows to prevent console window
        if os.name == 'nt':
            try:
                subprocess_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            except AttributeError:
                # CREATE_NO_WINDOW not available in this Python version, skip it
                pass
        
        result = subprocess.run(**subprocess_kwargs)
    except FileNotFoundError as exc:
        raise RuntimeError(
            "xelatex is not installed or not available in PATH. Please install it to generate PDFs."
        ) from exc
    except subprocess.TimeoutExpired:
        raise RuntimeError("PDF generation timed out after 60 seconds. The LaTeX file might be too complex or there's an issue with xelatex.")
    except Exception as exc:
        raise RuntimeError(f"Error during PDF generation: {str(exc)}")

    # Check if PDF was created
    if not os.path.exists(pdf_path):
        # Try to get error details from log file
        log_file = os.path.join(work_dir, f"{base_name}.log")
        error_details = ""
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    log_content = f.read()
                    # Extract error lines
                    error_lines = [line for line in log_content.split('\n') if '!' in line or 'Error' in line or 'Fatal' in line]
                    if error_lines:
                        error_details = "\n".join(error_lines[-10:])  # Last 10 error lines
            except Exception:
                pass
        
        raise RuntimeError(
            f"PDF generation failed (exit code {result.returncode}).\n"
            f"xelatex output:\n{result.stdout[-1000:] if result.stdout else 'No output'}\n"
            f"{error_details if error_details else ''}"
        )

    # Move LaTeX auxiliary files (.aux, .log, .out, .fls, .fdb_latexmk, .synctex.gz) to log folder
    log_dir = os.path.join(work_dir, "log")
    os.makedirs(log_dir, exist_ok=True)
    
    # List of common LaTeX auxiliary file extensions
    aux_extensions = [".aux", ".log", ".out", ".fls", ".fdb_latexmk", ".synctex.gz"]
    
    for ext in aux_extensions:
        aux_file = os.path.join(work_dir, f"{base_name}{ext}")
        if os.path.exists(aux_file):
            try:
                os.rename(aux_file, os.path.join(log_dir, f"{base_name}{ext}"))
            except Exception:
                pass  # Ignore if move fails

    if result.returncode != 0:
        # PDF was created but there were warnings
        pass

    return pdf_path


def record_invoice(fields, pdf_path):
    file_exists = os.path.exists(INVOICE_HISTORY_PATH) and os.path.getsize(INVOICE_HISTORY_PATH) > 0
    fieldnames = ["invoiceNumber", "invoiceDate", "billToName", "totalAmount", "filePath"]
    with open(INVOICE_HISTORY_PATH, "a", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(
            {
                "invoiceNumber": fields.get("invoiceNumber", ""),
                "invoiceDate": fields.get("invoiceDate", ""),
                "billToName": fields.get("billToName", ""),
                "totalAmount": fields.get("totalAmount", ""),
                "filePath": pdf_path,
            }
        )


def generate_invoice_pdf(fields, items):
    tex_path = render_invoice_tex(fields, items)
    pdf_path = compile_tex_to_pdf(tex_path)
    record_invoice(fields, pdf_path)
    return tex_path, pdf_path


def write_money_flow_entry(amount, category, note):
    timestamp = dt.datetime.now().isoformat(sep=" ", timespec="seconds")
    header_needed = not os.path.exists(MONEY_FLOW_PATH) or os.path.getsize(MONEY_FLOW_PATH) == 0
    with open(MONEY_FLOW_PATH, "a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        if header_needed:
            writer.writerow(["timestamp", "amount", "category", "note"])
        writer.writerow([timestamp, amount, category, note])


def calculate_productivity(hours, profit):
    if hours <= 0:
        raise ValueError("Hours worked per day must be greater than 0.")
    industrial_avg = 5411
    your_rate = (profit / 30) / hours
    productivity = (your_rate / industrial_avg) * 100
    return {
        "productivity": productivity,
        "daily_rate": profit / 30,
        "comparison": (
            "below" if your_rate < industrial_avg else "above" if your_rate > industrial_avg else "at"
        ),
    }


def calculate_tax(income, investment_deduction, health_insurance):
    standard_deduction = 50000
    investment_deduction = min(max(investment_deduction, 0), 150000)
    health_insurance = min(max(health_insurance, 0), 25000)

    total_deductions = standard_deduction + investment_deduction + health_insurance
    taxable_income = max(income - total_deductions, 0)

    tax = 0
    if taxable_income <= 250000:
        tax = 0
    elif taxable_income <= 500000:
        tax = (taxable_income - 250000) * 0.05
    elif taxable_income <= 1000000:
        tax = (250000 * 0.05) + (taxable_income - 500000) * 0.20
    else:
        tax = (250000 * 0.05) + (500000 * 0.20) + (taxable_income - 1000000) * 0.30

    if taxable_income <= 500000:
        tax = 0
        rebate_text = "Rebate under section 87A applied."
    else:
        rebate_text = "No rebate available."

    return {
        "taxable_income": taxable_income,
        "tax": round(tax, 2),
        "total_deductions": total_deductions,
        "rebate_text": rebate_text,
    }


PRO_TIPS = [
    r"Take regular breaks to maintain productivity.",
    r"Prioritize tasks using the Eisenhower Matrix.",
    r"Set specific goals for each work session.",
    r"Eliminate distractions by turning off notifications.",
    r"Use the Pomodoro Technique to manage time effectively.",
    r"Frame your product as a transformation tool, not a utility—sell the future state, not the feature list.",
    r"Mine competitor’s 1-star reviews to reverse-engineer your unique value proposition and preempt objections in copy.",
    r"Start with a premium offer and down-sell later—reverse funnels attract high-intent buyers with low acquisition cost.",
    r"Build a brand around one metric that matters—like “10x ROI in 30 days” or “zero churn.”",
    r"#HARD Use customer interviews to uncover latent needs—what they don’t know they want is often more valuable than what they do.",
    r"Invent a new category name for your product to avoid direct comparison and pricing pressure from incumbents.",
    r"Use a rolling 13-week cash flow model to forecast liquidity gaps before they become existential threats.",
    r"Pre-sell services with milestone-based billing to fund delivery without dipping into operational reserves.",
    r"Create a “minimum lovable product” that delights early adopters and builds word-of-mouth before scaling.",
    r"Use customer journey mapping to identify friction points and optimize conversion rates at every stage.",
    r"Leverage social proof by showcasing user-generated content—real results from real users build trust faster.",
    r"Create a “value ladder” of offerings that ascend in price and complexity, guiding customers to higher-value solutions.",
    r"Use scarcity tactics like limited-time offers or exclusive access to drive urgency and increase conversions.",
    r"Automate lead qualification with chatbots that ask key questions and route prospects to the right sales rep.",
    r"Use A/B testing to optimize landing pages, email campaigns, and ad creatives for maximum conversion.",
    r"Create a content syndication strategy to distribute your expertise across multiple platforms and reach new audiences.",
    r"Build a community around your brand—engage users in forums, social media, or Slack/Discord channels to foster loyalty and advocacy.",
    r"Factor invoices through fintech platforms to unlock cash early and reinvest before competitors even collect.",
    r"Split your bank accounts into profit-first envelopes—automate transfers to isolate savings from operational burn.",
    r"Use dynamic pricing algorithms that adjust based on demand signals, urgency, and customer segmentation tags.",
    r"Automate onboarding with conditional logic forms that route clients into tailored flows based on budget or goals.",
    r"Use n8n or Zapier to auto-generate invoices from form submissions and log them in your finance tracker.",
    r"Build a shadow CRM using Google Sheets and Apps Script—lightweight, scalable, and fully customizable.",
    r"Track internal assets using QR codes linked to Google Sheets for real-time inventory and location updates.",
    r"Auto-assign tasks based on keywords in incoming emails using a simple NLP classifier and webhook trigger.",
    r"Create a content calendar with Trello or Notion—visualize themes, deadlines, and publishing cadence.",
    r"Bundle your core service with complementary tools or templates to increase perceived value and reduce churn.",
    r"Create limited-edition versions of your product with countdown timers to drive urgency and exclusivity.",
    r"Use LaTeX to generate premium-looking invoices and reports that signal professionalism and justify pricing.",
    r"Offer white-label versions of your product to agencies who want to resell without building from scratch.",
    r"Use feedback loops to evolve pricing tiers based on actual usage patterns and customer willingness to pay.",
    r"Use Reddit and Quora to answer niche questions with embedded CTAs—organic traffic with high conversion intent.",
    r"Turn micro case studies into carousel posts for LinkedIn—each slide a hook, each metric a proof.",
    r"Pay users to post about your product instead of influencers—authenticity scales better than reach.",
    r"Build a referral engine with double-sided rewards and automated tracking—turn every customer into a marketer.",
    r"Use UTM parameters religiously to track every campaign, every click, and every conversion path across platforms.",
    r"Use async video onboarding to reduce training time and standardize knowledge transfer across remote hires.",
    r"Create a skill matrix for hiring decisions—map roles to capabilities, not just resumes or degrees.",
    r"Assign trial tasks before full-time offers—filter for execution, not just interview performance.",
    r"Automate payroll using conditional logic—trigger bonuses, deductions, and compliance filings without manual effort.",
    r"Build an internal wiki for SOPs—make tribal knowledge searchable, editable, and version-controlled.",
    r"Offer micro-equity to retain top talent—align incentives without diluting control or burning cash.",
    r"Gamify performance dashboards—turn KPIs into scoreboards that drive engagement and accountability.",
    r"Maintain a “talent pool” of pre-vetted freelancers—scale instantly without recruitment lag.",
    r"Create a “no-code” version of your product for non-technical users—expand your market without alienating devs.",
    r"Use AI to screen resumes by skill tags—filter for relevance, not keyword stuffing.",
    r"Automate feedback collection post-project—use forms and sentiment analysis to improve delivery cycles.",
    r"Sell unused domain names—your parked assets could be someone’s dream brand, and a quick cash win.",
    r"Create a business-in-a-box template—package your operations, branding, and SOPs for resale or licensing.",
    r"Use browser automation to scrape competitor pricing—stay ahead of market shifts without manual tracking.",
    r"Offer lifetime deals to fund early growth—front-load cash flow while building a loyal user base.",
    r"Run reverse auctions for vendor selection—let suppliers compete to offer you the best terms.",
    r"Test demand with a ghost product—launch a landing page before building anything to validate interest.",
    r"Simulate customer support with AI before hiring—train bots on FAQs and escalate only when needed.",
    r"Build internal micro-SaaS tools, then sell them—your ops solution might be someone else’s missing piece.",
    r"Turn your analytics into a product—offer dashboards or insights as a service to clients.",
    r"Create a profitability simulator—let clients model ROI before buying, increasing trust and conversion.",
    r"Use decision trees for client onboarding—route leads based on budget, urgency, and service fit.",
    r"Build a modular business model—each unit should be plug-and-play, scalable, and independently profitable.",
    r"Design your org chart around workflows, not hierarchy—optimize for throughput, not titles.",
    r"Use time-blocking for team operations—batch similar tasks to reduce context switching and increase velocity.",
    r"Create a “fail-fast” sandbox—test risky ideas in isolated environments before scaling.",
    r"Use version-controlled business plans—track pivots, assumptions, and learnings like a codebase.",
    r"Build a KPI tree—map every metric to its upstream driver and downstream impact.",
    r"Automate decision logging—record why choices were made to avoid repeating mistakes.",
    r"Use a “one-page strategy” doc—distill your entire business model into a visual map.",
    r"Create a feedback flywheel—every customer touchpoint should feed insights back into product or ops.",
    r"Trademark your internal frameworks—protect your methodology as intellectual capital.",
    r"License your onboarding flow to other agencies—turn your process into a revenue stream.",
    r"Create a proprietary scoring system—use it to evaluate clients, deals, or product fit.",
    r"Build a data moat—aggregate unique insights that competitors can’t easily replicate.",
    r"Use naming conventions as brand assets—own the language your market uses to describe your solution.",
    r"Integrate with platforms your users already love—reduce friction and increase adoption.",
    r"Offer embeddable widgets—let users bring your product into their own workflows.",
    r"Create a Zapier or n8n connector—unlock automation for power users and agencies.",
    r"Use webhooks to trigger external workflows—extend your product’s reach without building everything.",
    r"Build a plugin for a popular CMS or IDE—ride the wave of existing ecosystems.",
    r"Use the “regret minimization” framework for decisions—ask what future-you would wish you’d done.",
    r"Apply the “inversion” principle—ask how to fail, then avoid those paths deliberately.",
    r"Use the “barbell strategy”—balance safe bets with high-risk, high-reward experiments.",
    r"Apply the “80/20 of the 80/20”—find the 4% of actions that drive 64% of results.",
    r"Use “second-order thinking”—consider not just the immediate impact, but the ripple effects.",
    r"Build with exit in mind—structure your business so it can be sold, licensed, or franchised.",
    r"Create a valuation dashboard—track metrics that investors or acquirers care about.",
    r"Use deferred revenue models—lock in future cash flow while optimizing tax timing.",
    r"License your brand to regional operators—expand without managing every location.",
    r"Create a “silent partner” model—let others run your playbook while you earn passive income.",
    r"Document everything as if you’ll sell tomorrow—clarity and structure increase valuation instantly.",
]


def get_pro_tip():
    return r.choice(PRO_TIPS)


class SoloEntrepreneurApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Solo Entrepreneur Toolkit")
        self.geometry("960x640")
        self.minsize(900, 600)
        self.configure(bg="#f8f9fb")

        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background="#f8f9fb")
        style.configure("Header.TLabel", font=("Segoe UI", 20, "bold"))
        style.configure("Subheader.TLabel", font=("Segoe UI", 11))
        style.configure("Primary.TButton", font=("Segoe UI", 11), padding=8)

        container = ttk.Frame(self)
        container.pack(fill="both", expand=True)
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(0, weight=1)

        self.frames = {}
        for FrameClass in (
            HomeFrame,
            InvoiceFrame,
            TaxFrame,
            ProductivityFrame,
            MoneyMonitorFrame,
        ):
            frame = FrameClass(parent=container, controller=self)
            self.frames[FrameClass.__name__] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.show_frame("HomeFrame")

    def show_frame(self, name):
        frame = self.frames[name]
        frame.tkraise()


class HomeFrame(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        header = ttk.Label(self, text="Solo Entrepreneur Toolkit", style="Header.TLabel")
        header.pack(pady=(40, 10))
        subtitle = ttk.Label(
            self,
            text="Minimal desktop hub for invoicing, taxes, productivity, and money tracking.",
            style="Subheader.TLabel",
        )
        subtitle.pack(pady=(0, 30))

        buttons = [
            ("Invoice Generator", "InvoiceFrame"),
            ("Tax Calculator", "TaxFrame"),
            ("Productivity Calculator", "ProductivityFrame"),
            ("Money Monitor", "MoneyMonitorFrame"),
        ]

        grid = ttk.Frame(self)
        grid.pack()
        for idx, (label, frame_name) in enumerate(buttons):
            btn = ttk.Button(
                grid,
                text=label,
                style="Primary.TButton",
                command=lambda name=frame_name: controller.show_frame(name),
                width=28,
            )
            btn.grid(row=idx // 2, column=idx % 2, padx=15, pady=15, sticky="ew")


class InvoiceFrame(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.field_vars = {key: tk.StringVar(value="") for _, key in INVOICE_FIELD_KEYS}
        self.notes_text = tk.Text(self, height=4, width=40, font=("Segoe UI", 10))
        self.items = []

        # Header
        header_bar = ttk.Frame(self)
        header_bar.pack(fill="x", pady=(20, 10), padx=30)
        ttk.Button(header_bar, text="← Back", command=lambda: controller.show_frame("HomeFrame")).pack(
            side="left"
        )
        ttk.Label(header_bar, text="Invoice Generator", style="Header.TLabel").pack(side="left", padx=20)

        # Container for scrollable area
        scroll_container = ttk.Frame(self)
        scroll_container.pack(fill="both", expand=True, padx=0, pady=0)
        
        # Create scrollable canvas
        canvas = tk.Canvas(scroll_container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(scroll_container, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        def on_canvas_configure(event):
            canvas_width = event.width
            canvas.itemconfig(canvas_window, width=canvas_width)

        canvas.bind("<Configure>", on_canvas_configure)

        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", on_mousewheel)

        # Form fields in scrollable area
        form_frame = ttk.LabelFrame(scrollable_frame, text="Invoice Details")
        form_frame.pack(fill="x", padx=30, pady=10)
        for idx, (label, key) in enumerate(INVOICE_FIELD_KEYS):
            lbl = ttk.Label(form_frame, text=label)
            entry = ttk.Entry(form_frame, textvariable=self.field_vars[key])
            row, col = divmod(idx, 2)
            lbl.grid(row=row, column=col * 2, sticky="w", pady=4, padx=(10, 8))
            entry.grid(row=row, column=col * 2 + 1, sticky="ew", pady=4, padx=(0, 10))
            form_frame.grid_columnconfigure(col * 2 + 1, weight=1)

        # Notes section
        notes_frame = ttk.LabelFrame(scrollable_frame, text="Notes")
        notes_frame.pack(fill="x", padx=30, pady=10)
        self.notes_text.pack(in_=notes_frame, fill="x", padx=10, pady=10)

        # Items section
        items_frame = ttk.LabelFrame(scrollable_frame, text="Invoice Items")
        items_frame.pack(fill="both", expand=True, padx=30, pady=10)

        # Action buttons for items (above the tree)
        action_bar = ttk.Frame(items_frame)
        action_bar.pack(fill="x", padx=10, pady=(10, 5))
        ttk.Button(action_bar, text="+ Add Item", command=self.add_item_dialog).pack(side="left", padx=5)
        ttk.Button(action_bar, text="Remove Selected", command=self.remove_selected_item).pack(side="left", padx=5)

        # Treeview for items
        columns = ("itemName", "description", "quantity", "price", "tax", "amount")
        self.items_tree = ttk.Treeview(items_frame, columns=columns, show="headings", height=8)
        headings = ["Item", "Description", "Qty", "Price", "Tax %", "Amount"]
        widths = [120, 200, 60, 80, 60, 90]
        for col, heading, width in zip(columns, headings, widths):
            self.items_tree.heading(col, text=heading)
            self.items_tree.column(col, width=width, anchor="center")
        
        # Scrollbar for treeview
        tree_scroll = ttk.Scrollbar(items_frame, orient="vertical", command=self.items_tree.yview)
        self.items_tree.configure(yscrollcommand=tree_scroll.set)
        self.items_tree.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=(0, 10))
        tree_scroll.pack(side="right", fill="y", pady=(0, 10))

        # Pack canvas and scrollbar in container
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Footer with action buttons (always visible at bottom)
        footer = ttk.Frame(self)
        footer.pack(fill="x", padx=30, pady=15)
        ttk.Button(footer, text="Clear Form", command=self.reset_form).pack(side="left")
        self.generate_button = ttk.Button(footer, text="Generate Invoice PDF", style="Primary.TButton", command=self.generate_invoice)
        self.generate_button.pack(side="right")

    def reset_form(self):
        for var in self.field_vars.values():
            var.set("")
        self.notes_text.delete("1.0", tk.END)
        self.items.clear()
        for row in self.items_tree.get_children():
            self.items_tree.delete(row)
        # Clear total amount
        self.field_vars["totalAmount"].set("")

    def add_item_dialog(self):
        ItemDialog(self, self.add_item)

    def calculate_total_amount(self):
        """Calculate total amount by summing all item amounts"""
        total = 0.0
        for item in self.items:
            try:
                amount_str = item.get("amount", "0").strip().replace("₹", "").replace(",", "")
                if amount_str:
                    total += float(amount_str)
            except (ValueError, TypeError):
                continue
        return total

    def update_total_amount(self):
        """Update the totalAmount field with calculated total"""
        total = self.calculate_total_amount()
        # Format as currency with ₹ symbol
        formatted_total = f"₹{total:,.2f}"
        self.field_vars["totalAmount"].set(formatted_total)

    def add_item(self, item):
        self.items.append(item)
        self.items_tree.insert(
            "", "end", values=(item["itemName"], item["description"], item["quantity"], item["price"], item["tax"], item["amount"])
        )
        # Auto-update total amount
        self.update_total_amount()

    def remove_selected_item(self):
        selected = self.items_tree.selection()
        if not selected:
            messagebox.showinfo("Remove Item", "Select a row to remove.")
            return
        index = self.items_tree.index(selected[0])
        self.items_tree.delete(selected[0])
        self.items.pop(index)
        # Auto-update total amount
        self.update_total_amount()

    def generate_invoice(self):
        # Update total amount before generating
        self.update_total_amount()
        
        fields = blank_invoice_fields()
        for _, key in INVOICE_FIELD_KEYS:
            fields[key] = self.field_vars[key].get().strip()
        fields["notesText"] = self.notes_text.get("1.0", tk.END).strip()
        if not fields["invoiceNumber"]:
            fields["invoiceNumber"] = dt.datetime.now().strftime("%Y%m%d-%H%M")
        if not fields["invoiceDate"]:
            fields["invoiceDate"] = dt.datetime.now().strftime("%d/%m/%Y")
        if not self.items:
            proceed = messagebox.askyesno(
                "No Items Added",
                "No items were added to the invoice. Generate an empty invoice?",
            )
            if not proceed:
                return
        
        # Disable the generate button to prevent multiple clicks
        self.generate_button.config(state="disabled")
        
        # Show progress dialog (non-modal to allow updates)
        progress_window = tk.Toplevel(self)
        progress_window.title("Generating PDF")
        progress_window.geometry("350x120")
        progress_window.transient(self)
        progress_window.resizable(False, False)
        
        # Center the progress window
        progress_window.update_idletasks()
        x = (progress_window.winfo_screenwidth() // 2) - (progress_window.winfo_width() // 2)
        y = (progress_window.winfo_screenheight() // 2) - (progress_window.winfo_height() // 2)
        progress_window.geometry(f"+{x}+{y}")
        
        status_label = ttk.Label(progress_window, text="Generating invoice PDF...\nPlease wait...", justify="center")
        status_label.pack(pady=20)
        progress_window.update()
        
        # Store references for callbacks
        self._progress_window = progress_window
        self._status_label = status_label
        
        def generate_in_background():
            try:
                # Update status
                self.after(0, lambda: status_label.config(text="Creating LaTeX file...\nPlease wait..."))
                self.after(0, lambda: progress_window.update())
                
                tex_path, pdf_path = generate_invoice_pdf(fields, self.items)
                
                # Schedule UI updates on main thread
                self.after(0, lambda p=pdf_path: on_success(p))
            except Exception as exc:
                # Schedule error display on main thread
                error_msg = str(exc)
                self.after(0, lambda e=error_msg: on_error(e))
        
        def on_success(pdf_path):
            try:
                if self._progress_window and self._progress_window.winfo_exists():
                    self._progress_window.destroy()
            except Exception:
                pass
            if self.generate_button:
                self.generate_button.config(state="normal")
            messagebox.showinfo(
                "Success",
                f"Invoice PDF generated successfully!\n\nSaved to:\n{pdf_path}",
            )
            # Return to home page
            self.controller.show_frame("HomeFrame")
        
        def on_error(error_msg):
            try:
                if self._progress_window and self._progress_window.winfo_exists():
                    self._progress_window.destroy()
            except Exception:
                pass
            if self.generate_button:
                self.generate_button.config(state="normal")
            # Show detailed error message
            messagebox.showerror("Invoice Error", f"Failed to generate PDF:\n\n{error_msg}")
        
        # Start PDF generation in background thread
        thread = threading.Thread(target=generate_in_background, daemon=True)
        thread.start()
        
        # Periodically check if thread is still alive and update UI
        def check_thread():
            if thread.is_alive():
                # Thread still running, continue waiting
                self.after(100, check_thread)
            else:
                # Thread finished but no callback was called - might be an issue
                # This shouldn't happen if exceptions are caught properly
                pass
        
        self.after(100, check_thread)


class ItemDialog(tk.Toplevel):
    def __init__(self, parent, callback):
        super().__init__(parent)
        self.title("Add Invoice Item")
        self.callback = callback
        self.resizable(False, False)
        self.grab_set()

        fields = [
            ("Item Name", "itemName"),
            ("Description", "description"),
            ("Quantity", "quantity"),
            ("Price (₹)", "price"),
            ("Tax (%)", "tax"),
            ("Amount (₹)", "amount"),
        ]
        self.vars = {}
        for idx, (label, key) in enumerate(fields):
            ttk.Label(self, text=label).grid(row=idx, column=0, sticky="e", padx=10, pady=6)
            entry = ttk.Entry(self)
            entry.grid(row=idx, column=1, padx=10, pady=6)
            self.vars[key] = entry
            
            # Bind auto-calculation for quantity, price, and tax
            if key in ["quantity", "price", "tax"]:
                entry.bind("<KeyRelease>", self.calculate_amount)
                entry.bind("<FocusOut>", self.calculate_amount)

        # Make amount field read-only (auto-calculated)
        self.vars["amount"].config(state="readonly")
        
        button_frame = ttk.Frame(self)
        button_frame.grid(row=len(fields), column=0, columnspan=2, pady=10)
        ttk.Button(button_frame, text="Cancel", command=self.destroy).pack(side="right", padx=5)
        ttk.Button(button_frame, text="Add", command=self.submit).pack(side="right")

    def calculate_amount(self, event=None):
        """Calculate amount = (quantity * price) * (1 + tax/100)"""
        try:
            quantity_str = self.vars["quantity"].get().strip()
            price_str = self.vars["price"].get().strip()
            tax_str = self.vars["tax"].get().strip()
            
            if not quantity_str or not price_str:
                self.vars["amount"].config(state="normal")
                self.vars["amount"].delete(0, tk.END)
                self.vars["amount"].config(state="readonly")
                return
            
            quantity = float(quantity_str)
            price = float(price_str)
            tax = float(tax_str) if tax_str else 0.0
            
            # Calculate: (quantity * price) * (1 + tax/100)
            amount = (quantity * price) * (1 + tax / 100)
            
            self.vars["amount"].config(state="normal")
            self.vars["amount"].delete(0, tk.END)
            self.vars["amount"].insert(0, f"{amount:.2f}")
            self.vars["amount"].config(state="readonly")
        except (ValueError, TypeError):
            # If invalid input, clear amount field
            self.vars["amount"].config(state="normal")
            self.vars["amount"].delete(0, tk.END)
            self.vars["amount"].config(state="readonly")

    def submit(self):
        item = {key: entry.get().strip() for key, entry in self.vars.items()}
        if not item["itemName"]:
            messagebox.showwarning("Validation", "Item name is required.")
            return
        if not item["quantity"] or not item["price"]:
            messagebox.showwarning("Validation", "Quantity and Price are required.")
            return
        # Amount is auto-calculated, so we use the value from the field
        if not item["amount"]:
            self.calculate_amount()
            item["amount"] = self.vars["amount"].get().strip()
        self.callback(item)
        self.destroy()


class TaxFrame(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        header_bar = ttk.Frame(self)
        header_bar.pack(fill="x", pady=(20, 10), padx=30)
        ttk.Button(header_bar, text="← Back", command=lambda: controller.show_frame("HomeFrame")).pack(side="left")
        ttk.Label(header_bar, text="Tax Calculator", style="Header.TLabel").pack(side="left", padx=20)

        form = ttk.Frame(self)
        form.pack(padx=30, pady=20, fill="x")

        self.income_var = tk.DoubleVar(value=0)
        self.invest_var = tk.DoubleVar(value=0)
        self.health_var = tk.DoubleVar(value=0)

        ttk.Label(form, text="Yearly Income (₹)").grid(row=0, column=0, sticky="w", pady=8)
        ttk.Entry(form, textvariable=self.income_var).grid(row=0, column=1, sticky="ew", pady=8)
        ttk.Label(form, text="Investment under 80C (max ₹150000)").grid(row=1, column=0, sticky="w", pady=8)
        ttk.Entry(form, textvariable=self.invest_var).grid(row=1, column=1, sticky="ew", pady=8)
        ttk.Label(form, text="Health Insurance under 80D (max ₹25000)").grid(row=2, column=0, sticky="w", pady=8)
        ttk.Entry(form, textvariable=self.health_var).grid(row=2, column=1, sticky="ew", pady=8)
        form.grid_columnconfigure(1, weight=1)

        ttk.Button(self, text="Calculate Tax", style="Primary.TButton", command=self.handle_calculation).pack(
            padx=30, pady=10, anchor="w"
        )

        self.result_label = ttk.Label(self, text="", style="Subheader.TLabel", justify="left")
        self.result_label.pack(fill="x", padx=30)

    def handle_calculation(self):
        try:
            result = calculate_tax(self.income_var.get(), self.invest_var.get(), self.health_var.get())
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            return
        self.result_label.config(
            text=(
                f"Taxable Income: ₹{result['taxable_income']:.2f}\n"
                f"Total Deductions: ₹{result['total_deductions']:.2f}\n"
                f"Tax Payable: ₹{result['tax']:.2f}\n"
                f"{result['rebate_text']}\n"
                "File ITR-3/4 as applicable and retain proofs."
            )
        )


class ProductivityFrame(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        header_bar = ttk.Frame(self)
        header_bar.pack(fill="x", pady=(20, 10), padx=30)
        ttk.Button(header_bar, text="← Back", command=lambda: controller.show_frame("HomeFrame")).pack(side="left")
        ttk.Label(header_bar, text="Productivity Calculator", style="Header.TLabel").pack(side="left", padx=20)

        form = ttk.Frame(self)
        form.pack(padx=30, pady=20, fill="x")

        self.hours_var = tk.DoubleVar(value=0)
        self.profit_var = tk.DoubleVar(value=0)

        ttk.Label(form, text="Hours Worked Per Day").grid(row=0, column=0, sticky="w", pady=8)
        ttk.Entry(form, textvariable=self.hours_var).grid(row=0, column=1, sticky="ew", pady=8)
        ttk.Label(form, text="Profit Per Month (₹)").grid(row=1, column=0, sticky="w", pady=8)
        ttk.Entry(form, textvariable=self.profit_var).grid(row=1, column=1, sticky="ew", pady=8)
        form.grid_columnconfigure(1, weight=1)

        ttk.Button(self, text="Calculate Productivity", style="Primary.TButton", command=self.handle_calc).pack(
            padx=30, pady=10, anchor="w"
        )
        self.result_label = ttk.Label(self, text="", style="Subheader.TLabel", justify="left")
        self.result_label.pack(fill="x", padx=30)

    def handle_calc(self):
        try:
            result = calculate_productivity(self.hours_var.get(), self.profit_var.get())
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            return
        tip = get_pro_tip()
        self.result_label.config(
            text=(
                f"Productivity: {result['productivity']:.2f}% of industry benchmark\n"
                f"Daily Earnings: ₹{result['daily_rate']:.2f}\n"
                f"You are {result['comparison']} the ₹5411/hr benchmark.\n"
                f"Pro Tip: {tip}"
            )
        )


class MoneyMonitorFrame(ttk.Frame):
    CATEGORIES = [
        "Sales Revenue",
        "Customer Prepayments",
        "Royalties & Licensing",
        "Investment Returns",
        "Grants & Subsidies",
        "Financing Activities",
        "Asset Liquidation",
        "Affiliate/Referral",
        "Rent & Utilities",
        "Salaries & Wages",
        "Software Licenses",
        "Raw Materials / Inventory",
        "Taxes & Compliance",
        "Insurance",
        "Branding & Design",
        "Team Retreats / Perks",
        "Premium Tools",
        "Marketing Campaigns",
        "Office Decor / Furniture",
        "R&D",
        "Capital Expenditure",
        "Hiring for Scale",
        "Market Expansion",
        "Training & Upskilling",
        "Data Infrastructure",
    ]

    def __init__(self, parent, controller):
        super().__init__(parent)
        header_bar = ttk.Frame(self)
        header_bar.pack(fill="x", pady=(20, 10), padx=30)
        ttk.Button(header_bar, text="← Back", command=lambda: controller.show_frame("HomeFrame")).pack(side="left")
        ttk.Label(header_bar, text="Money Monitor", style="Header.TLabel").pack(side="left", padx=20)

        form = ttk.Frame(self)
        form.pack(padx=30, pady=20, fill="x")

        ttk.Label(form, text="Category").grid(row=0, column=0, sticky="w", pady=8)
        self.category_var = tk.StringVar(value=self.CATEGORIES[0])
        category_combo = ttk.Combobox(form, textvariable=self.category_var, values=self.CATEGORIES, state="readonly")
        category_combo.grid(row=0, column=1, sticky="ew", pady=8)

        ttk.Label(form, text="Amount (₹)").grid(row=1, column=0, sticky="w", pady=8)
        self.amount_var = tk.DoubleVar(value=0)
        ttk.Entry(form, textvariable=self.amount_var).grid(row=1, column=1, sticky="ew", pady=8)

        ttk.Label(form, text="Note").grid(row=2, column=0, sticky="w", pady=8)
        self.note_entry = ttk.Entry(form)
        self.note_entry.grid(row=2, column=1, sticky="ew", pady=8)
        form.grid_columnconfigure(1, weight=1)

        ttk.Button(self, text="Save Entry", style="Primary.TButton", command=self.save_entry).pack(
            padx=30, pady=10, anchor="w"
        )

        self.status_label = ttk.Label(self, text="", style="Subheader.TLabel", justify="left")
        self.status_label.pack(fill="x", padx=30)

    def save_entry(self):
        amount = self.amount_var.get()
        if amount == 0:
            messagebox.showwarning("Validation", "Amount should not be zero.")
            return
        note = self.note_entry.get().strip() or "None"
        try:
            write_money_flow_entry(amount, self.category_var.get(), note)
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            return
        self.status_label.config(
            text=f"Saved {self.category_var.get()} entry for ₹{amount:.2f}.\nLogged at {MONEY_FLOW_PATH}."
        )
        self.note_entry.delete(0, tk.END)
        self.amount_var.set(0)


if __name__ == "__main__":
    app = SoloEntrepreneurApp()
    app.mainloop()
import csv
# import time
# fill_invoice.py
import os
import re
import random as r
import datetime as dt



# variables for LaTeX templete
companyName,companyAddress,companyCity,companyCountry,companyPostal,billToName,billToAddress,billToCity,billToCountry,billToPostal,invoiceNumber,invoiceDate,invoiceDueDate,notesText,totalAmount="","","","","","","","","","","","","","",""
# Values to replace with in latex code in the generated latex file
fields = {
    'companyName': companyName,
    'companyAddress': companyAddress,
    'companyCity': companyCity,
    'companyCountry': companyCountry,
    'companyPostal': companyPostal,
    'billToName': billToName,
    'billToAddress': billToAddress,
    'billToCity': billToCity,
    'billToCountry': billToCountry,
    'billToPostal': billToPostal,
    'invoiceNumber': invoiceNumber,
    'invoiceDate': invoiceDate,
    'invoiceDueDate': invoiceDueDate,
    'notesText': notesText,
    'totalAmount': totalAmount
}



# Example items list (each item is a dict)
items = [
#    {'itemName': 'Mini Notebook', 'description': 'Handmade 20-page mini notebook', 'quantity': '3', 'price': '₹150', 'tax': '0%', 'amount': '₹450'}, this is the format 
]


def getInvoiceFields():
    noOfItems=int(input("Enter the Number of Items to put in the invoice: "))
    for i in fields.keys():
        fields[i]=input(f"Enter {i}: ")
    for i in range(noOfItems):
        tempd={}
        itemName = input("Enter itemName: ")
        description = input("Enter description: ")
        quantity = input("Enter quantity: ")
        price = input("Enter price: ")
        tax = input("Enter tax: ")
        amount = input("Enter amount: ")
        tempd["itemName"]=str(itemName)
        tempd["description"]=str(description)
        tempd["quantity"]=str(quantity)
        tempd["price"]=str("₹"+str(price))
        tempd["tax"]=str(str(tax)+"%")
        tempd["amount"]=str("₹"+str(amount))
        items.append(tempd)
    return fields,items                                    


def createInvoice():
    """Generate invoice .tex files from CSV. Returns list of generated file paths."""
    generated_files = []
    csv_path = 'C:\\Users\\aditk\\Desktop\\Solo Entrepreneur ToolKit\\invoiceHistory.csv'
    
    # Handle missing CSV gracefully
    if not os.path.exists(csv_path):
        return generated_files
    
    with open(csv_path, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            # Update fields dictionary with CSV row data
            for key in fields.keys():
                if key in row:
                    fields[key] = row[key]

            # create item rows from CSV data
            items = []
            for i in range(1, 6):  # Assuming up to 5 items
                item_key = f'item{i}Name'
                if item_key in row and row[item_key]:
                    item = {
                        'itemName': row[item_key],
                        'description': row.get(f'item{i}Description', ''),
                        'quantity': row.get(f'item{i}Quantity', '1'),
                        'price': row.get(f'item{i}Price', '0'),
                        'tax': row.get(f'item{i}Tax', '0%'),
                        'amount': row.get(f'item{i}Amount', '0')
                    }
                    items.append(item)

            # read and replace template using a callback to avoid regex backreference issues
            template_path = 'C:\\Users\\aditk\\Desktop\\Solo Entrepreneur ToolKit\\invoiceTemplate.tex'
            if not os.path.exists(template_path):
                continue  # Skip if template is missing
            
            with open(template_path, 'r') as f:
                tex = f.read()
            
            def replace_field(match):
                """Callback to safely replace field values without regex backreference interference."""
                key = match.group(1)
                val = fields.get(key, '')
                return match.group(0).split('{')[0] + '{' + val + '}'
            
            pattern = r'(\\newcommand\{\\([^}]+)\}\{)[^\}]*\}'
            tex = re.sub(pattern, replace_field, tex)

            # adds items to the space where required
            rows = []
            for it in items:
                row = r'{' + it['itemName'] + '}&{' + it['description'] + '}&{' + it['quantity'] + '}&{₹' + it['price'] + '}&{' + it['tax'] + '%}&{₹' + it['amount'] + '}\\'
                rows.append(row)

            rows_text = '\n'.join(rows)
            tex = tex.replace('%%ITEM_ROWS%%', rows_text)

            # unique filename creator
            base_dir = r"C:\Users\aditk\Desktop\Solo Entrepreneur ToolKit"
            invoice_number = (fields.get('invoiceNumber') or '0000').replace('/', '-').strip()
            output_tex_path = os.path.join(base_dir, f"invoice_{invoice_number}.tex")
            with open(output_tex_path, 'w', encoding='utf-8') as f:
                f.write(tex)
            generated_files.append(output_tex_path)
            print(f"Generated {output_tex_path}")
    
    return generated_files

def recordInvoice(output_tex_file, csv_path=None):
    """Record invoice to CSV. csv_path defaults to invoiceHistory.csv in BASE_DIR."""
    if csv_path is None:
        csv_path = INVOICE_HISTORY_PATH
    
    fieldnames = ['invoiceNumber', 'invoiceDate', 'billToName', 'totalAmount', 'filePath']
    file_exists = os.path.exists(csv_path)
    
    with open(csv_path, 'a', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if not file_exists or (os.path.exists(csv_path) and os.stat(csv_path).st_size == 0):
            writer.writeheader()
        writer.writerow({
            'invoiceNumber': fields.get('invoiceNumber', ''),
            'invoiceDate': fields.get('invoiceDate', ''),
            'billToName': fields.get('billToName', ''),
            'totalAmount': fields.get('totalAmount', ''),
            'filePath': output_tex_file
        })

##########################################################################################################################################################

def moneyMonitor_record(choice_index, amount, note, file_path=None):
    """Record a money flow entry without interactive input. Returns the category used."""
    if file_path is None:
        file_path = MONEY_FLOW_PATH
    
    categories = [
        "Sales Revenue",
        "Customer Prepayments",
        "Royalties & Licensing",
        "Investment Returns",
        "Grants & Subsidies",
        "Financing Activities",
        "Asset Liquidation",
        "Affiliate/Referral",
        "Rent & Utilities",
        "Salaries & Wages",
        "Software Licenses",
        "Raw Materials / Inventory",
        "Taxes & Compliance",
        "Insurance",
        "Branding & Design",
        "Team Retreats / Perks",
        "Premium Tools",
        "Marketing Campaigns",
        "Office Decor / Furniture",
        "R&D",
        "Capital Expenditure",
        "Hiring for Scale",
        "Market Expansion",
        "Training & Upskilling",
        "Data Infrastructure"
    ]
    if choice_index < 0 or choice_index >= len(categories):
        raise IndexError(f"Invalid category index {choice_index}")
    
    category = categories[choice_index]
    os.makedirs(os.path.dirname(file_path) or '.', exist_ok=True)
    with open(file_path, 'a', encoding='utf-8') as f:
        f.write(f"{dt.datetime.now()},{amount},{category},{note}\n")
    return category


def proTip():
    tips = [
        r"Take regular breaks to maintain productivity.",
        r"Prioritize tasks using the Eisenhower Matrix.",
        r"Set specific goals for each work session.",
        r"Eliminate distractions by turning off notifications.",
        r"Use the Pomodoro Technique to manage time effectively.",
        r"Frame your product as a transformation tool, not a utility—sell the future state, not the feature list.",
        r"Mine competitor’s 1-star reviews to reverse-engineer your unique value proposition and preempt objections in copy.",
        r"Start with a premium offer and down-sell later—reverse funnels attract high-intent buyers with low acquisition cost.",
        r"Build a brand around one metric that matters—like “10x ROI in 30 days” or “zero churn.”",
        r"#HARD Use customer interviews to uncover latent needs—what they don’t know they want is often more valuable than what they do.",
        r"Invent a new category name for your product to avoid direct comparison and pricing pressure from incumbents.",
        r"Use a rolling 13-week cash flow model to forecast liquidity gaps before they become existential threats.",
        r"Pre-sell services with milestone-based billing to fund delivery without dipping into operational reserves.",
        r"Create a “minimum lovable product” that delights early adopters and builds word-of-mouth before scaling.",
        r"Use customer journey mapping to identify friction points and optimize conversion rates at every stage.",
        r"Leverage social proof by showcasing user-generated content—real results from real users build trust faster.",
        r"Create a “value ladder” of offerings that ascend in price and complexity, guiding customers to higher-value solutions.",
        r"Use scarcity tactics like limited-time offers or exclusive access to drive urgency and increase conversions.",
        r"Automate lead qualification with chatbots that ask key questions and route prospects to the right sales rep.",
        r"Use A/B testing to optimize landing pages, email campaigns, and ad creatives for maximum conversion.",
        r"Create a content syndication strategy to distribute your expertise across multiple platforms and reach new audiences.",
        r"Build a community around your brand—engage users in forums, social media, or Slack/Discord channels to foster loyalty and advocacy.",
        r"Factor invoices through fintech platforms to unlock cash early and reinvest before competitors even collect.",
        r"Split your bank accounts into profit-first envelopes—automate transfers to isolate savings from operational burn.",
        r"Use dynamic pricing algorithms that adjust based on demand signals, urgency, and customer segmentation tags.",
        r"Automate onboarding with conditional logic forms that route clients into tailored flows based on budget or goals.",
        r"Use n8n or Zapier to auto-generate invoices from form submissions and log them in your finance tracker.",
        r"Build a shadow CRM using Google Sheets and Apps Script—lightweight, scalable, and fully customizable.",
        r"Track internal assets using QR codes linked to Google Sheets for real-time inventory and location updates.",
        r"Auto-assign tasks based on keywords in incoming emails using a simple NLP classifier and webhook trigger.",
        r"Create a content calendar with Trello or Notion—visualize themes, deadlines, and publishing cadence.",
        r"Bundle your core service with complementary tools or templates to increase perceived value and reduce churn.",
        r"Create limited-edition versions of your product with countdown timers to drive urgency and exclusivity.",
        r"Use LaTeX to generate premium-looking invoices and reports that signal professionalism and justify pricing.",
        r"Offer white-label versions of your product to agencies who want to resell without building from scratch.",
        r"Use feedback loops to evolve pricing tiers based on actual usage patterns and customer willingness to pay.",
        r"Use Reddit and Quora to answer niche questions with embedded CTAs—organic traffic with high conversion intent.",
        r"Turn micro case studies into carousel posts for LinkedIn—each slide a hook, each metric a proof.",
        r"Pay users to post about your product instead of influencers—authenticity scales better than reach.",
        r"Build a referral engine with double-sided rewards and automated tracking—turn every customer into a marketer.",
        r"Use UTM parameters religiously to track every campaign, every click, and every conversion path across platforms.",
        r"Use async video onboarding to reduce training time and standardize knowledge transfer across remote hires.",#
        r"Create a skill matrix for hiring decisions—map roles to capabilities, not just resumes or degrees.",
        r"Assign trial tasks before full-time offers—filter for execution, not just interview performance.",
        r"Automate payroll using conditional logic—trigger bonuses, deductions, and compliance filings without manual effort.",
        r"Build an internal wiki for SOPs—make tribal knowledge searchable, editable, and version-controlled.",
        r"Offer micro-equity to retain top talent—align incentives without diluting control or burning cash.",
        r"Gamify performance dashboards—turn KPIs into scoreboards that drive engagement and accountability.",
        r"Maintain a “talent pool” of pre-vetted freelancers—scale instantly without recruitment lag.",
        r"Create a “no-code” version of your product for non-technical users—expand your market without alienating devs.",
        r"Use AI to screen resumes by skill tags—filter for relevance, not keyword stuffing.",
        r"Automate feedback collection post-project—use forms and sentiment analysis to improve delivery cycles.",
        r"Sell unused domain names—your parked assets could be someone’s dream brand, and a quick cash win.",
        r"Create a business-in-a-box template—package your operations, branding, and SOPs for resale or licensing.", 
        r"Use browser automation to scrape competitor pricing—stay ahead of market shifts without manual tracking.",
        r"Offer lifetime deals to fund early growth—front-load cash flow while building a loyal user base.",
        r"Run reverse auctions for vendor selection—let suppliers compete to offer you the best terms.",
        r"Test demand with a ghost product—launch a landing page before building anything to validate interest.",
        r"Simulate customer support with AI before hiring—train bots on FAQs and escalate only when needed.",
        r"Build internal micro-SaaS tools, then sell them—your ops solution might be someone else’s missing piece.",
        r"Turn your analytics into a product—offer dashboards or insights as a service to clients.",
        r"Create a profitability simulator—let clients model ROI before buying, increasing trust and conversion.",
        r"Use decision trees for client onboarding—route leads based on budget, urgency, and service fit.",
        r"Build a modular business model—each unit should be plug-and-play, scalable, and independently profitable.",    
        r"Design your org chart around workflows, not hierarchy—optimize for throughput, not titles.",
        r"Use time-blocking for team operations—batch similar tasks to reduce context switching and increase velocity.",
        r"Create a “fail-fast” sandbox—test risky ideas in isolated environments before scaling.",
        r"Use version-controlled business plans—track pivots, assumptions, and learnings like a codebase.",
        r"Build a KPI tree—map every metric to its upstream driver and downstream impact.",
        r"Automate decision logging—record why choices were made to avoid repeating mistakes.",
        r"Use a “one-page strategy” doc—distill your entire business model into a visual map.",
        r"Create a feedback flywheel—every customer touchpoint should feed insights back into product or ops.",
        r"Trademark your internal frameworks—protect your methodology as intellectual capital.",
        r"License your onboarding flow to other agencies—turn your process into a revenue stream.",
        r"Create a proprietary scoring system—use it to evaluate clients, deals, or product fit.",
        r"Build a data moat—aggregate unique insights that competitors can’t easily replicate.",
        r"Use naming conventions as brand assets—own the language your market uses to describe your solution.",
        r"Integrate with platforms your users already love—reduce friction and increase adoption.",
        r"Offer embeddable widgets—let users bring your product into their own workflows.",
        r"Create a Zapier or n8n connector—unlock automation for power users and agencies.",
        r"Use webhooks to trigger external workflows—extend your product’s reach without building everything.",
        r"Build a plugin for a popular CMS or IDE—ride the wave of existing ecosystems.",
        r"Use the “regret minimization” framework for decisions—ask what future-you would wish you’d done.",
        r"Apply the “inversion” principle—ask how to fail, then avoid those paths deliberately.",
        r"Use the “barbell strategy”—balance safe bets with high-risk, high-reward experiments.",
        r"Apply the “80/20 of the 80/20”—find the 4% of actions that drive 64% of results.",
        r"Use “second-order thinking”—consider not just the immediate impact, but the ripple effects.",
        r"Build with exit in mind—structure your business so it can be sold, licensed, or franchised.",
        r"Create a valuation dashboard—track metrics that investors or acquirers care about.",
        r"Use deferred revenue models—lock in future cash flow while optimizing tax timing.",
        r"License your brand to regional operators—expand without managing every location.", 
        r"Create a “silent partner” model—let others run your playbook while you earn passive income.",
        r"Document everything as if you’ll sell tomorrow—clarity and structure increase valuation instantly."
    ]
    i = r.randint(0, len(tips) - 1)
    print("Pro Tip: \n" + tips[i])


def printMoneyFlowChart():#outline for moneyMonitor Module and its part
    print('''
Inflow:
1)    Sales Revenue
2)    Customer Prepayments
3)    Royalties & Licensing
4)    Investment Returns
5)    Grants & Subsidies
6)    Financing Activities
7)    Asset Liquidation
8)    Affiliate/Referral
Outflow:
    Needs:
    9)    Rent & Utilities
    10)   Salaries & Wages
    11)   Software Licenses
    12)   Raw Materials / Inventory
    13)   Taxes & Compliance  
    14)   Insurance
    Wants:
    15)   Branding & Design
    16)   Team Retreats / Perks
    17)   Premium Tools
    18)   Marketing Campaigns
    19)   Office Decor / Furniture
    Investments:
    20)   R&D
    21)   Capital Expenditure
    22)   Hiring for Scale
    23)   Market Expansion
    24)   Training & Upskilling
    25)   Data Infrastructure
''')

def getMoneyData():
    pass

def getInvoiceData():
    pass

def productivityCalculator(hrsWorkedPerDay=None, profitPerMonth=None):
    """Calculate and return productivity percentage. If params not provided, prompt user."""
    if hrsWorkedPerDay is None:
        hrsWorkedPerDay = int(input("Enter hrs Worked Per Day:"))
    if profitPerMonth is None:
        profitPerMonth = int(input("Enter profit Per Month:"))
    
    if hrsWorkedPerDay == 0:
        return 0.0
    industrialAvg = 5411.0   # industrial average productivity in ₹/hr
    yourRate = (profitPerMonth / 30.0) / float(hrsWorkedPerDay)
    productivity = ((yourRate / industrialAvg) * 100.0)
    
    # Print if parameters were provided (not in test mode)
    print(f"Your productivity is {productivity:.2f}%")
    if yourRate < industrialAvg:
        print(f"You are at ₹{(profitPerMonth/30):.2f} i.e. below the industrial average of ₹{industrialAvg}.\n")
    elif yourRate > industrialAvg:
        print(f"You are at ₹{(profitPerMonth/30):.2f} i.e. above the industrial average of ₹{industrialAvg}.\n")
    else:
        print(f"You are at ₹{(profitPerMonth/30):.2f} i.e. meeting the industrial average of ₹{industrialAvg}.\n")
    proTip()
    
    return productivity


def compileInvoiceGenerator():
    import subprocess
    createInvoice()
    # Assuming the last generated invoice is the one to record
    print("----- INVOICE gENERATOR -----")
    invoice_number = fields.get('invoiceNumber', '0000').replace('/', '-')
    output_tex_file = f'invoice_{invoice_number}.tex'
    recordInvoice(output_tex_file)
    
    # Compile .tex to .pdf using pdflatex
    base_dir = r"C:\Users\aditk\Desktop\Solo Entrepreneur ToolKit"
    tex_path = os.path.join(base_dir, output_tex_file)
    
    if not os.path.exists(tex_path):
        print(f"ERROR: {tex_path} not found.")
        return
    
    # Run pdflatex twice (first pass for references, second for final output)
    for run in range(1, 3):
        print(f"\nCompiling (pass {run}/2)...")
        try:
            result = subprocess.run(
                ['pdflatex', '-interaction=nonstopmode', '-halt-on-error', output_tex_file],
                cwd=base_dir,
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode != 0:
                print(f"ERROR (pass {run}): pdflatex failed.")
                print(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
                if result.stderr:
                    print(result.stderr[-500:] if len(result.stderr) > 500 else result.stderr)
                return
        except Exception as e:
            print(f"ERROR: Failed to run pdflatex: {e}")
            return
    
    pdf_file = output_tex_file.replace('.tex', '.pdf')
    pdf_path = os.path.join(base_dir, pdf_file)
    if os.path.exists(pdf_path):
        print(f"\n✅ PDF generated successfully: {pdf_path}")
    else:
        print(f"WARNING: PDF file not found at {pdf_path}")
    
def moneyMonitor():
    print("----- MONEY MONITOR -----")
    printMoneyFlowChart()
    choice = int(input("Enter the number of your category: "))

    categories = [
        "Sales Revenue",
        "Customer Prepayments",
        "Royalties & Licensing",
        "Investment Returns",
        "Grants & Subsidies",
        "Financing Activities",
        "Asset Liquidation",
        "Affiliate/Referral",
        "Rent & Utilities",
        "Salaries & Wages",
        "Software Licenses",
        "Raw Materials / Inventory",
        "Taxes & Compliance",
        "Insurance",
        "Branding & Design",
        "Team Retreats / Perks",
        "Premium Tools",
        "Marketing Campaigns",
        "Office Decor / Furniture",
        "R&D",
        "Capital Expenditure",
        "Hiring for Scale",
        "Market Expansion",
        "Training & Upskilling",
        "Data Infrastructure"
    ]

    category = categories[choice-1]
    amount = input("Enter amount: ")
    note="None"
    note = input("Enter note: ")

    with open("C:\\Users\\aditk\\Desktop\\Solo Entrepreneur ToolKit\\moneyFlow.csv", "a") as f:
        f.write(f"{dt.datetime.now()},{amount},{category},{note}\n")

    print(f"\n Entry saved successfully under '{category}' category!\n")
    f.close()




def taxCalculator():
    print("----- TAX CALCULATOR -----")

    income = float(input("enter your yearly income (in ₹): "))

    standard_deduction = 50000
    print("standard deduction of ₹", standard_deduction, "is applied.")

    investment_deduction = float(input("enter investment under 80C (max ₹150000): "))
    if investment_deduction > 150000:
        investment_deduction = 150000
        print("only ₹150000 allowed under 80C, taking that.")

    health_insurance = float(input("enter health insurance premium under 80D (max ₹25000): "))
    if health_insurance > 25000:
        health_insurance = 25000
        print("only ₹25000 allowed under 80D, taking that.")

    total_deductions = standard_deduction + investment_deduction + health_insurance
    print("total deductions applied: ₹", total_deductions)

    taxable_income = income - total_deductions
    if taxable_income < 0:
        taxable_income = 0
    print("taxable income: ₹", taxable_income)

    tax = 0
    if taxable_income <= 250000:
        tax = 0
    elif taxable_income <= 500000:
        tax = (taxable_income - 250000) * 0.05
    elif taxable_income <= 1000000:
        tax = (250000 * 0.05) + (taxable_income - 500000) * 0.20
    else:
        tax = (250000 * 0.05) + (500000 * 0.20) + (taxable_income - 1000000) * 0.30

    if taxable_income <= 500000:
        print("rebate under section 87A applied.")
        tax = 0

    print("--------------------------------")
    print("final income tax payable: ₹", round(tax, 2))
    print("--------------------------------")
    print("Note:")
    print("- keep all proofs for deductions claimed.")
    print("- file ITR-3 or ITR-4 as applicable.")
    print("- consider GST registration if turnover > ₹20 lakh.")
    print("--------------------------------")


if __name__ == "__main__":
    while True:
            print("""
    Welcome to Solo Entrepreneur Toolkit\nMenu
    1) Invoice Generator
    2) Tax Calculator
    3) Productivity Calculator
    4) Money Monitor
    5) Exit
    """)
            choice = input("Choose an option (1-5): ")
            if choice == '1':
                compileInvoiceGenerator()
            elif choice == '2':
                taxCalculator()
            elif choice == '3':
                productivityCalculator()
            elif choice == '4':
                moneyMonitor()
            elif choice == '5':
                print("Exiting.\nHave a nice time ahead.")
                break
            else:
                print("Invalid option. Please choose between 1 and 5.")
