from django.core.management.base import BaseCommand
from apartments.models import Apartment, ApartmentImages, LeasingCompany


class Command(BaseCommand):
    help = "Clear apartment data. Optionally restrict to a specific leasing company."

    def add_arguments(self, parser):
        parser.add_argument(
            "--company",
            type=str,
            help="Name of leasing company to clear (optional)"
        )

    def handle(self, *args, **options):
        company_name = options.get("company")

        if company_name:
            companies = LeasingCompany.objects.filter(name__icontains=company_name)

            if not companies.exists():
                self.stdout.write(self.style.ERROR(f"No leasing company found matching '{company_name}'"))
                return

            total_images = 0
            total_apartments = 0
            total_companies = 0

            for company in companies:
                apartments = Apartment.objects.filter(leasingCompany=company)

                image_count = ApartmentImages.objects.filter(apartment__in=apartments).count()
                apartment_count = apartments.count()

                ApartmentImages.objects.filter(apartment__in=apartments).delete()
                apartments.delete()
                company.delete()

                total_images += image_count
                total_apartments += apartment_count
                total_companies += 1

            self.stdout.write(self.style.SUCCESS(
                f"Deleted {total_images} ApartmentImages, "
                f"{total_apartments} Apartments, "
                f"{total_companies} LeasingCompanies matching '{company_name}'."
            ))

        else:
            image_count = ApartmentImages.objects.count()
            apartment_count = Apartment.objects.count()
            company_count = LeasingCompany.objects.count()

            ApartmentImages.objects.all().delete()
            Apartment.objects.all().delete()
            LeasingCompany.objects.all().delete()

            self.stdout.write(self.style.SUCCESS(
                f"Deleted {image_count} ApartmentImages, "
                f"{apartment_count} Apartments, "
                f"{company_count} LeasingCompanies."
            ))