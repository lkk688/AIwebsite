import Hero from "@/components/Hero";
import About from "@/components/About";
import Brands from "@/components/Brands";
import GridImageView from "@/components/GridImageView";
import Products from "@/components/Products";
import Services from "@/components/Services";
import Contact from "@/components/Contact";
import Facility from "@/components/Facility";
import Certifications from "@/components/Certifications";

export default function Home() {
  return (
    <div className="flex flex-col">
      <Hero />
      <About />
      <Facility />
      <Certifications />
      <Brands />
      <GridImageView />
      <Products />
      <Services />
      <Contact />
    </div>
  );
}
