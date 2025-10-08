import csv
import time
# fill_invoice.py
import os
import re
import random as r
import datetime as dt



# Default values for LaTeX macros
companyName,companyAddress,companyCity,companyCountry,companyPostal,billToName,billToAddress,billToCity,billToCountry,billToPostal,invoiceNumber,invoiceDate,invoiceDueDate,notesText,totalAmount="","","","","","","","","","","","","","",""
# Values to replace (camelCase keys match LaTeX macro names)
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
#    {'itemName': 'Mini Notebook', 'description': 'Handmade 20-page mini notebook', 'quantity': '3', 'price': '₹150', 'tax': '0%', 'amount': '₹450'},
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
    # Read CSV file
    with open('invoiceHistory.csv', 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            # Update fields dictionary with CSV row data
            for key in fields.keys():
                if key in row:
                    fields[key] = row[key]

            # Generate item rows from CSV data
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

            # Read template
            with open('invoiceTemplate.tex', 'r') as f:
                tex = f.read()

            # Replace macro default values using regex
            for key, val in fields.items():
                pattern = r'(\\newcommand\{\\' + re.escape(key) + r'\}\{)[^\}]*\}'
                replacement = r'\1' + val + '}'
                tex, n = re.subn(pattern, replacement, tex)

            # Generate item rows using \addItem macro
            rows = []
            for it in items:
                row = r'{' + it['itemName'] + '}&{' + it['description'] + '}&{' + it['quantity'] + '}&{₹' + it['price'] + '}&{' + it['tax'] + '\%}&{₹' + it['amount'] + '}\\'
                rows.append(row)

            rows_text = '\n'.join(rows)
            tex = tex.replace('%%ITEM_ROWS%%', rows_text)

            # Save filled tex with unique filename
            invoice_number = fields.get('invoiceNumber', '0000').replace('/', '-')
            output_tex_file = f'invoice_{invoice_number}.tex'
            with open(output_tex_file, 'w') as f:
                f.write(tex)
            print(f"Generated {output_tex_file}")

def recordInvoice(output_tex_file):
    # Append invoice details to CSV file
    with open("invoiceHistory.csv", 'a', newline='') as csvfile:
        fieldnames = ['invoiceNumber', 'invoiceDate', 'billToName', 'totalAmount', 'filePath']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        # Write header if file is new
        if os.stat("invoiceHistory.csv").st_size == 0:
            writer.writeheader()

        writer.writerow({
            'invoiceNumber': fields.get('invoiceNumber', ''),
            'invoiceDate': fields.get('invoiceDate', ''),
            'billToName': fields.get('billToName', ''),
            'totalAmount': fields.get('totalAmount', ''),
            'filePath': output_tex_file
        })

##########################################################################################################################################################

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
    Sales Revenue
    Customer Prepayments
    Royalties & Licensing
    Investment Returns
    Grants & Subsidies
    Financing Activities
    Asset Liquidation
    Affiliate/Referral
Outflow:
    Needs:
        Rent & Utilities
        Salaries & Wages
        Software Licenses
        Raw Materials / Inventory
        Taxes & Compliance  
        Insurance
    Wants:
        Branding & Design
        Team Retreats / Perks
        Premium Tools
        Marketing Campaigns
        Office Decor / Furniture
    Investments:
        R&D
        Capital Expenditure
        Hiring for Scale
        Market Expansion
        Training & Upskilling
        Data Infrastructure
''')

def getMoneyData():
    pass

def moneyMonitor(amount,category,note):
    f=open('moneyFlow.csv','a+')
    f.write(f"{dt.datetime.now()},{amount},{category},{note}\n")
    f.close()


def productivityCalculator(hrsWorkedPerDay, profitPerMonth):
    if hrsWorkedPerDay == 0:
        return 0
    industrialAvg = 5411  # Example industrial average productivity in ₹/hr
    yourRate = (profitPerMonth / 30) / hrsWorkedPerDay
    productivity = ((yourRate/industrialAvg) * 100)
    print(f"Your productivity is {productivity}%")
    if yourRate < industrialAvg:
        print(f"You are below the industrial average of {industrialAvg}%.\n")
    elif yourRate > industrialAvg:
        print(f"You are above the industrial average of {industrialAvg}%.\n")
    else:
        print(f"You are meeting the industrial average of {industrialAvg}%.\n")
    proTip()

if __name__ == "__main__":
    createInvoice()
    # Assuming the last generated invoice is the one to record
    invoice_number = fields.get('invoiceNumber', '0000').replace('/', '-')
    output_tex_file = f'invoice_{invoice_number}.tex'
    recordInvoice(output_tex_file)
    os.system(f'pdflatex {output_tex_file}')